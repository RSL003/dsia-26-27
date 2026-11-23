"""Uniones temporales y SQLite con respuestas de API simuladas, sin red."""
import json
from io import BytesIO
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from aire_app import download_air, enrich
from aire_app.cli import main
from aire_app.loader import AireLoader
from aire_app.validator import AireValidator

MUESTRA = Path(__file__).parent / "fixtures/aire_muestra.csv"


def aire_fecha(fecha):
    frame = AireLoader().cargar(MUESTRA)
    frame.loc[0, ["ANO", "MES", "DIA"]] = fecha.split("-")
    for h in range(1, 25):
        frame[f"H{h:02}"] = "10"
        frame[f"V{h:02}"] = "V"
    return frame


def respuesta(url):
    query = parse_qs(urlparse(url).query)
    inicio = pd.Timestamp(query["start_date"][0], tz="UTC")
    fin = pd.Timestamp(query["end_date"][0], tz="UTC") + pd.Timedelta(hours=23)
    horas = pd.date_range(inicio, fin, freq="h")
    hourly = {k: [1.] * len(horas) for k in enrich.VARIABLES}
    hourly["time"] = (horas.astype("int64") // 10**9).tolist()
    return json.dumps({"latitude": 40.4, "longitude": -3.7, "utc_offset_seconds": 0,
                       "hourly_units": {"temperature_2m": "°C", "relative_humidity_2m": "%",
                                        "wind_speed_10m": "m/s", "wind_direction_10m": "°",
                                        "precipitation": "mm"}, "hourly": hourly}).encode()


@pytest.mark.parametrize("fecha,h01,h24", [
    ("2025-01-01", "2025-01-01T00:00:00Z", "2025-01-01T23:00:00Z"),
    ("2025-07-01", "2025-06-30T23:00:00Z", "2025-07-01T22:00:00Z"),
])
def test_fin_bloque_invierno_verano(fecha, h01, h24):
    validos, _ = AireValidator().validar(aire_fecha(fecha))
    resultado = enrich.preparar_aire(validos)
    assert resultado.iloc[0].timestamp_utc == h01
    assert resultado.iloc[-1].timestamp_utc == h24
    assert resultado.estado_tiempo.eq("ok").all()


@pytest.mark.parametrize("fecha", ["2025-03-30", "2025-10-26"])
def test_no_adivina_intervalos_cambio_horario(fecha):
    validos, _ = AireValidator().validar(aire_fecha(fecha))
    resultado = enrich.preparar_aire(validos).set_index("hora")
    assert resultado.loc[["H02", "H03"], "timestamp_utc"].isna().all()
    assert resultado.loc["H04", "estado_tiempo"] == "ok"


def test_sqlite_union_cache_y_fallos(tmp_path, monkeypatch):
    entrada = tmp_path / "aire.csv"
    frame = aire_fecha("2025-03-30")
    frame.to_csv(entrada, sep=";", index=False)
    validos, _ = AireValidator().validar(frame)
    codigo = enrich.preparar_aire(validos).iloc[0].estacion_id
    catalogo = tmp_path / "estaciones.csv"
    catalogo.write_text(f"CODIGO;ESTACION;LATITUD;LONGITUD\n{codigo};Prueba;40.4;-3.7\n")
    cache, db = tmp_path / "cache", tmp_path / "base.sqlite"
    monkeypatch.setattr(enrich, "descargar", respuesta)
    informe = enrich.construir_base(entrada, catalogo, cache, db)
    assert informe["observaciones_aire"] == 24
    assert informe["con_fila_meteo"] == 22
    assert informe["tiempo_no_resuelto"] == 2
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM aire_enriquecido").fetchone()[0] == 24
        assert con.execute("SELECT temperature_2m FROM aire_enriquecido WHERE hora='H04'").fetchone()[0] == 1
        assert con.execute("SELECT temperature_2m FROM aire_enriquecido WHERE hora='H02'").fetchone()[0] is None
    monkeypatch.setattr(enrich, "descargar", lambda url: pytest.fail("No debe usar red"))
    assert enrich.construir_base(entrada, catalogo, cache, db, offline=True)["con_fila_meteo"] == 22
    anterior = db.read_bytes()
    next(cache.glob("*.meta.json")).write_text('{}')
    with pytest.raises(KeyError):
        enrich.construir_base(entrada, catalogo, cache, db, offline=True)
    assert db.read_bytes() == anterior


def test_unidades_y_duplicados_api():
    url = enrich.ENDPOINT + "?start_date=2025-01-01&end_date=2025-01-01"
    datos = json.loads(respuesta(url))
    datos["hourly"]["time"][1] = datos["hourly"]["time"][0]
    with pytest.raises(ValueError, match="duplicada"):
        enrich.interpretar_meteo(json.dumps(datos).encode(), "28079004")
    datos["hourly_units"]["wind_speed_10m"] = "km/h"
    with pytest.raises(ValueError, match="Unidades"):
        enrich.interpretar_meteo(json.dumps(datos).encode(), "28079004")


def test_pipeline_actualizado_se_detiene_si_falta_la_serie(tmp_path, monkeypatch, capsys):
    """La descarga contiene otra estación: quedan los datos auditados, sin predicción antigua."""
    monkeypatch.setattr(download_air, "urlopen", lambda url, timeout: BytesIO(MUESTRA.read_bytes()))
    monkeypatch.setattr(enrich, "descargar", respuesta)
    for _ in range(2):
        assert main(["pipeline", "--actualizar", "--output", str(tmp_path)]) == 1
        assert "No hay datos para la estación 28079004" in capsys.readouterr().err
    ejecuciones = list(tmp_path.iterdir())
    assert len(ejecuciones) == 2
    for ejecucion in ejecuciones:
        assert (ejecucion / "datos/aire.origen.local.json").is_file()
        assert (ejecucion / "calidad/resumen.json").is_file()
        assert (ejecucion / "aire.sqlite").is_file()
        assert not (ejecucion / "inferencia").exists()
