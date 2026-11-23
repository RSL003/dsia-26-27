"""Ejecuta carga, validación, métricas y exportación desde la terminal."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .exceptions import VentasError
from .loader import VentasLoader
from .metrics import calcular_metricas
from .validator import VentasValidator

BASE = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    """Exporta tres artefactos; devuelve 1 ante errores controlados."""
    parser = argparse.ArgumentParser(description="Pipeline de calidad de ventas")
    parser.add_argument("--input", type=Path, default=BASE / "datos/ventas/ventas.csv")
    parser.add_argument("--output", type=Path, default=BASE / "resultados/ventas")
    args = parser.parse_args(argv)
    try:
        frame = VentasLoader().cargar(args.input)
        validos, errores = VentasValidator().validar(frame)
        resumen = calcular_metricas(validos, len(frame))
        contenido = json.dumps(resumen, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        args.output.mkdir(parents=True, exist_ok=True)
        validos.to_csv(args.output / "ventas_limpias.csv", index=False, date_format="%Y-%m-%d")
        errores.to_csv(args.output / "ventas_rechazadas.csv", index=False)
        (args.output / "calidad_datos.json").write_text(contenido, encoding="utf-8")
    except (VentasError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Ventas: {len(frame)} filas; {len(validos)} válidas; {len(errores)} rechazadas.")
    print(f"Importe total válido: {resumen['importe_total']:.2f}. Resultados: {args.output}")
    return 0
