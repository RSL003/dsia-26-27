"""Ejecuta el análisis de aire con una copia local reproducible."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .exceptions import AireError
from .loader import AireLoader
from .validator import AireValidator
from .metrics import calcular_metricas

BASE = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    """Carga, valida y exporta el CSV municipal y su resumen."""
    parser = argparse.ArgumentParser(description="Calidad de datos de aire de Madrid")
    parser.add_argument("--input", type=Path, default=BASE / "datos/internet/aire.csv")
    parser.add_argument("--output", type=Path, default=BASE / "resultados/aire")
    args = parser.parse_args(argv)
    try:
        frame = AireLoader().cargar(args.input)
        validos, errores = AireValidator().validar(frame)
        resumen = calcular_metricas(validos, errores, len(frame))
        contenido = json.dumps(resumen, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        args.output.mkdir(parents=True, exist_ok=True)
        validos.to_csv(args.output / "aire_limpio.csv", index=False, date_format="%Y-%m-%d")
        errores.to_csv(args.output / "aire_excluido.csv", index=False, date_format="%Y-%m-%d")
        (args.output / "resumen.json").write_text(contenido, encoding="utf-8")
    except (AireError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Aire: {len(frame)} filas originales; {len(validos)} observaciones utilizables; {len(errores)} excluidas.")
    return 0
