"""Ejecuta el análisis de aire con una copia local reproducible."""
from __future__ import annotations
import argparse
import csv
import logging
from pathlib import Path
import sqlite3
import sys

from pandas.errors import DatabaseError

from .exceptions import AireError
from .orquestador import ejecutar_completo, ejecutar_inferencia, ejecutar_pipeline

BASE = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    """Selecciona la ejecución completa, la inferencia o la auditoría del CSV."""
    argv = sys.argv[1:] if argv is None else argv
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if argv[:1] == ["pipeline"]:
        return ejecutar_pipeline_cli(argv[1:])
    if argv[:1] == ["run"]:
        return ejecutar_run(argv[1:])
    parser = argparse.ArgumentParser(
        description="Calidad de datos de aire de Madrid",
        epilog="Usa 'pipeline --help' para todo el proceso o 'run --help' para cargar un modelo entrenado.",
    )
    parser.add_argument("--input", type=Path, default=BASE / "datos/aire.csv")
    parser.add_argument("--output", type=Path, default=BASE / "resultados")
    args = parser.parse_args(argv)
    try:
        total, validos, errores = ejecutar_pipeline(args.input, args.output)
    except (AireError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Aire: {total} filas originales; {validos} observaciones utilizables; {errores} excluidas.")
    return 0


def ejecutar_pipeline_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m aire_app pipeline",
                                     description="Valida el aire, integra ERA5, entrena, predice y genera el informe")
    parser.add_argument("--output", type=Path, default=BASE / "resultados/ejecuciones",
                        help="Directorio donde crear una carpeta por ejecución")
    parser.add_argument("--actualizar", action="store_true",
                        help="Descarga aire municipal y ERA5 en lugar de usar la serie incluida")
    parser.add_argument("--ai-mode", choices=("mock", "real"), default="mock",
                        help="Informe local o mediante Hugging Face")
    args = parser.parse_args(argv)
    try:
        ejecucion = ejecutar_completo(BASE / "datos", args.output, args.actualizar, args.ai_mode)
    except (AireError, OSError, ValueError, KeyError, TypeError, sqlite3.Error, DatabaseError, csv.Error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(ejecucion)
    return 0


def ejecutar_run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m aire_app run",
                                     description="Predice la hora siguiente desde SQLite")
    parser.add_argument("--database", type=Path, default=BASE / "datos/aire_meteo.sqlite")
    parser.add_argument("--models", type=Path, default=BASE / "modelos")
    parser.add_argument("--output", type=Path, default=BASE / "resultados/inferencia")
    parser.add_argument("--ai-mode", choices=("mock", "real"), default="mock",
                        help="Informe local (mock) o Hugging Face Inference (real)")
    args = parser.parse_args(argv)
    try:
        ejecutar_inferencia(args.database, args.models, args.output, args.ai_mode)
    except (AireError, OSError, ValueError, KeyError, TypeError, sqlite3.Error, DatabaseError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0
