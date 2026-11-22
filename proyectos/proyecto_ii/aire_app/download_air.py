"""Descarga explícita de una copia del CSV municipal, sin ejecutar al importar."""
import csv
import hashlib
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

URL = (
    "https://datos.madrid.es/dataset/201200-0-calidad-aire-horario/"
    "resource/201200-1-calidad-aire-horario-csv/"
    "download/201200-1-calidad-aire-horario-csv.csv"
)


def descargar():
    """Guarda CSV y manifiesto solo si la respuesta tiene el encabezado esperado."""
    with urlopen(URL, timeout=60) as respuesta:
        contenido = respuesta.read()
    lector = csv.reader(io.StringIO(contenido.decode("utf-8-sig")), delimiter=";")
    encabezado = next(lector, [])
    requeridas = {"PROVINCIA", "MUNICIPIO", "ESTACION", "MAGNITUD", "PUNTO_MUESTREO", "ANO", "MES", "DIA"}
    for hora in range(1, 25):
        requeridas.update([f"H{hora:02}", f"V{hora:02}"])
    if not requeridas.issubset(encabezado):
        raise ValueError("La respuesta no contiene el esquema horario esperado")
    filas = 0
    for fila in lector:
        if len(fila) != len(encabezado):
            raise ValueError("El CSV contiene una fila con un número incorrecto de campos")
        filas += 1
    if not filas:
        raise ValueError("El CSV municipal no contiene datos")
    carpeta = Path(__file__).resolve().parents[1] / "datos"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "aire.csv").write_bytes(contenido)
    manifiesto = {
        "url": URL,
        "descarga_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(contenido).hexdigest(),
        "licencia": "CC BY 4.0",
        "fuente": "Ayuntamiento de Madrid",
        "dataset": "Calidad del aire. Datos horarios desde 2001. Desde 2025",
        "actualizacion": "Mensual",
        "filas_originales": filas,
    }
    (carpeta / "aire.origen.local.json").write_text(json.dumps(manifiesto, indent=2) + "\n", encoding="utf-8")
    print(f"Guardadas {filas} filas en {carpeta / 'aire.csv'}")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        descargar()
    except (OSError, ValueError, csv.Error) as exc:
        logging.error("No se pudo descargar el CSV municipal: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
