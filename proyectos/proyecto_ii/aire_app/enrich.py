"""Descarga meteorología histórica y construye una SQLite reproducible.

Ejecutar con python -m aire_app.enrich --help. No entrena modelos.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import pandas as pd

from .exceptions import AireError
from .loader import AireLoader
from .validator import AireValidator

BASE = Path(__file__).resolve().parents[1]
VARIABLES = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m",
             "wind_direction_10m", "precipitation"]
ESTACIONES_URL = (
    "https://datos.madrid.es/dataset/212629-0-estaciones-control-aire/resource/"
    "212629-0-estaciones-control-aire-csv/download/212629-0-estaciones-control-aire-csv.csv"
)
ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"
LOG = logging.getLogger(__name__)


def cargar_estaciones(ruta: Path) -> pd.DataFrame:
    """Normaliza los códigos y las coordenadas decimales del catálogo municipal."""
    raw = pd.read_csv(ruta, sep=";", encoding="utf-8-sig", dtype=str)
    frame = raw[["CODIGO", "ESTACION", "LATITUD", "LONGITUD"]].rename(columns={
        "CODIGO": "estacion_id", "ESTACION": "nombre", "LATITUD": "latitud",
        "LONGITUD": "longitud"})
    for col in ["latitud", "longitud"]:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    if (frame.isna().any().any() or frame.estacion_id.duplicated().any()
            or not frame.latitud.between(-90, 90).all()
            or not frame.longitud.between(-180, 180).all()):
        raise ValueError("Catálogo de estaciones inválido")
    return frame


def formatear_utc(instantes: pd.Series) -> pd.Series:
    utc = instantes.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy(dtype="datetime64[s]")
    texto = np.datetime_as_string(utc, unit="s", timezone="UTC")
    return pd.Series(texto, index=instantes.index).mask(np.isnat(utc))


def preparar_aire(validos: pd.DataFrame) -> pd.DataFrame:
    """Convierte bloques locales a final UTC; no adivina horas de cambio horario."""
    frame = validos.copy()
    frame["estacion_id"] = (frame.PROVINCIA.str.zfill(2)
                            + frame.MUNICIPIO.str.zfill(3) + frame.ESTACION.str.zfill(3))
    fin = frame.fecha + pd.to_timedelta(frame.hora.str[1:].astype(int), unit="h")
    inicio = fin - pd.Timedelta(hours=1)
    fin_utc = fin.dt.tz_localize("Europe/Madrid", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    inicio_utc = inicio.dt.tz_localize("Europe/Madrid", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    correcto = (fin_utc - inicio_utc).eq(pd.Timedelta(hours=1))
    frame["timestamp_utc"] = formatear_utc(fin_utc.where(correcto))
    frame["estado_tiempo"] = np.where(correcto, "ok", "cambio_horario_no_resuelto")
    frame["fecha"] = frame.fecha.dt.strftime("%Y-%m-%d")
    return frame


def url_meteo(estacion, inicio: str, fin: str) -> str:
    """Fija modelo, unidades y UTC para que las descargas sean comparables."""
    return ENDPOINT + "?" + urlencode({
        "latitude": estacion.latitud, "longitude": estacion.longitud,
        "start_date": inicio, "end_date": fin, "hourly": ",".join(VARIABLES),
        "models": "era5", "timezone": "GMT", "timeformat": "unixtime",
        "wind_speed_unit": "ms", "temperature_unit": "celsius",
        "precipitation_unit": "mm"})


def descargar(url: str) -> bytes:
    """Reintenta únicamente límites temporales y errores de servidor."""
    for intento in range(4):
        try:
            with urlopen(url, timeout=120) as respuesta:
                return respuesta.read()
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or intento == 3:
                raise
            espera = min(60, 20 * (intento + 1))
            LOG.warning("HTTP %s; reintento en %s segundos", exc.code, espera)
            time.sleep(espera)
    raise RuntimeError("No se pudo descargar")


def interpretar_meteo(contenido: bytes, estacion_id: str) -> pd.DataFrame:
    """Valida estructura, unidades y valores; conserva nulos sin imputar."""
    data = json.loads(contenido)
    esperadas = {"temperature_2m": "°C", "relative_humidity_2m": "%",
                 "wind_speed_10m": "m/s", "wind_direction_10m": "°", "precipitation": "mm"}
    if data.get("utc_offset_seconds") != 0 or any(
        data.get("hourly_units", {}).get(k) != v for k, v in esperadas.items()
    ):
        raise ValueError("Unidades o zona horaria inesperadas en meteorología")
    raw = data["hourly"]
    frame = pd.DataFrame({k: raw[k] for k in ["time"] + VARIABLES})
    instantes = pd.to_datetime(frame.pop("time"), unit="s", utc=True)
    frame["timestamp_utc"] = formatear_utc(instantes)
    if frame.empty or frame.timestamp_utc.duplicated().any():
        raise ValueError("Serie meteorológica vacía o duplicada")
    for col in VARIABLES:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
        if np.isinf(frame[col]).any():
            raise ValueError("Meteorología con valores no finitos")
    for col, bajo, alto in [("relative_humidity_2m", 0, 100), ("wind_direction_10m", 0, 360)]:
        if not frame[col].dropna().between(bajo, alto).all():
            raise ValueError(f"Fuera de rango: {col}")
    if (frame[["wind_speed_10m", "precipitation"]] < 0).any().any():
        raise ValueError("Viento o precipitación negativos")
    frame["estacion_id"] = estacion_id
    frame["modelo"] = "era5"
    frame["celda_latitud"] = data["latitude"]
    frame["celda_longitud"] = data["longitude"]
    return frame


def construir_base(entrada: Path, catalogo: Path, cache: Path, destino: Path,
                   offline: bool = False) -> dict:
    """Descarga/cachea por estación y publica la base solo después de validarla."""
    validos, errores = AireValidator().validar(AireLoader().cargar(entrada))
    aire = preparar_aire(validos)
    tiempos = aire.timestamp_utc.dropna()
    if tiempos.empty:
        raise ValueError("No hay observaciones con tiempo resoluble")
    estaciones = cargar_estaciones(catalogo)
    faltan = set(aire.estacion_id) - set(estaciones.estacion_id)
    if faltan:
        raise ValueError(f"Estaciones sin coordenadas: {sorted(faltan)}")
    estaciones = estaciones.loc[estaciones.estacion_id.isin(aire.estacion_id)].copy()
    inicio, fin = tiempos.min()[:10], tiempos.max()[:10]
    cache.mkdir(parents=True, exist_ok=True)
    meteorologia, fuentes = [], []
    for estacion in estaciones.itertuples(index=False):
        url = url_meteo(estacion, inicio, fin)
        clave = hashlib.sha256(url.encode()).hexdigest()[:16]
        archivo = cache / f"{estacion.estacion_id}_{clave}.json"
        manifiesto = archivo.with_suffix(".meta.json")
        LOG.info("Meteorología %s: %s a %s", estacion.estacion_id, inicio, fin)
        if archivo.exists() and manifiesto.exists():
            contenido = archivo.read_bytes()
            meta = json.loads(manifiesto.read_text())
            if meta["url"] != url or meta["sha256"] != hashlib.sha256(contenido).hexdigest():
                raise ValueError(f"Caché alterada: {archivo}")
        else:
            if offline:
                raise ValueError(f"Falta caché meteorológica: {archivo}")
            contenido = descargar(url)
            interpretar_meteo(contenido, estacion.estacion_id)
            meta = {"url": url, "descarga_utc": datetime.now(timezone.utc).isoformat(),
                    "sha256": hashlib.sha256(contenido).hexdigest(), "proveedor": "Open-Meteo / ERA5",
                    "licencia": "CC BY 4.0", "estacion_id": estacion.estacion_id}
            archivo.write_bytes(contenido)
            manifiesto.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
        meteorologia.append(interpretar_meteo(contenido, estacion.estacion_id))
        fuentes.append(meta)
    meteo = pd.concat(meteorologia, ignore_index=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{destino.name}-", dir=destino.parent) as carpeta:
        temporal = Path(carpeta) / destino.name
        with closing(sqlite3.connect(temporal)) as con, con:
            aire.to_sql("aire", con, if_exists="replace", index=False, chunksize=10000)
            meteo.to_sql("meteorologia", con, if_exists="replace", index=False)
            estaciones.to_sql("estaciones", con, if_exists="replace", index=False)
            pd.DataFrame(fuentes).to_sql("fuentes_meteo", con, if_exists="replace", index=False)
            con.executescript('''
                DROP VIEW IF EXISTS aire_enriquecido;
                CREATE UNIQUE INDEX IF NOT EXISTS idx_meteo ON meteorologia(estacion_id, timestamp_utc);
                CREATE INDEX IF NOT EXISTS idx_aire ON aire(estacion_id, timestamp_utc);
                CREATE VIEW aire_enriquecido AS
                SELECT a.*, e.nombre AS nombre_estacion, e.latitud, e.longitud,
                       m.temperature_2m, m.relative_humidity_2m, m.wind_speed_10m,
                       m.wind_direction_10m, m.precipitation,
                       CASE WHEN m.timestamp_utc IS NULL THEN 0 ELSE 1 END AS meteo_disponible
                FROM aire a JOIN estaciones e ON a.estacion_id = e.estacion_id
                LEFT JOIN meteorologia m ON a.estacion_id = m.estacion_id
                                       AND a.timestamp_utc = m.timestamp_utc;
            ''')
            total, unidos = con.execute("SELECT COUNT(*), SUM(meteo_disponible) FROM aire_enriquecido").fetchone()
            if total != len(aire):
                raise ValueError("La unión ha alterado el número de observaciones")
            informe = {"observaciones_aire": total, "aire_excluido_validacion": len(errores),
                       "con_fila_meteo": unidos, "sin_fila_meteo": total - unidos,
                       "tiempo_no_resuelto": int(aire.timestamp_utc.isna().sum()),
                       "filas_meteo": len(meteo), "estaciones": len(estaciones),
                       "periodo_utc": [inicio, fin], "modelo_meteo": "era5",
                       "nulos_meteo_por_variable": {k: int(meteo[k].isna().sum()) for k in VARIABLES},
                       "aire_sha256": hashlib.sha256(entrada.read_bytes()).hexdigest(),
                       "catalogo_sha256": hashlib.sha256(catalogo.read_bytes()).hexdigest(),
                       "catalogo_url": ESTACIONES_URL,
                       "creacion_utc": datetime.now(timezone.utc).isoformat()}
            pd.DataFrame([{"json": json.dumps(informe)}]).to_sql("ejecucion", con, if_exists="replace", index=False)
        temporal.replace(destino)
    destino.with_suffix(".resumen.json").write_text(json.dumps(informe, indent=2) + "\n")
    return informe


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=BASE / "datos/aire.csv")
    parser.add_argument("--stations", type=Path, default=BASE / "datos/estaciones.csv")
    parser.add_argument("--cache", type=Path, default=BASE / "datos/meteo_cache")
    parser.add_argument("--database", type=Path, default=BASE / "datos/aire_meteo.sqlite")
    parser.add_argument("--offline", action="store_true", help="Reutiliza caché sin acceso a red")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        informe = construir_base(args.input, args.stations, args.cache, args.database, args.offline)
    except (AireError, OSError, ValueError, KeyError, sqlite3.Error, URLError) as exc:
        LOG.error("No se ha publicado una base nueva: %s", exc)
        return 1
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
