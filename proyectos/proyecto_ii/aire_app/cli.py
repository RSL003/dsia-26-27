"""Ejecuta el análisis de aire con una copia local reproducible."""
from __future__ import annotations
import argparse
import logging
from pathlib import Path
import sqlite3
import sys

from pandas.errors import DatabaseError

from .exceptions import AireError
from .orquestador import ejecutar_inferencia, ejecutar_pipeline

BASE = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    """Carga, valida y exporta el CSV municipal y su resumen."""
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["run"]:
        return ejecutar_run(argv[1:])
    parser = argparse.ArgumentParser(
        description="Calidad de datos de aire de Madrid",
        epilog="Para generar una predicción, usa python -m aire_app run --help.",
    )
    parser.add_argument("--input", type=Path, default=BASE / "datos/aire.csv")
    parser.add_argument("--output", type=Path, default=BASE / "resultados")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        total, validos, errores = ejecutar_pipeline(args.input, args.output)
    except (AireError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Aire: {total} filas originales; {validos} observaciones utilizables; {errores} excluidas.")
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
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        ejecutar_inferencia(args.database, args.models, args.output, args.ai_mode)
    except (AireError, OSError, ValueError, KeyError, TypeError, sqlite3.Error, DatabaseError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0
