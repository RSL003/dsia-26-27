"""Punto de entrada del paquete: argumentos, ejecución y resultados."""

import argparse
import json
import logging
from pathlib import Path

from .loader import (
    CsvSalesRepository,
    DataLoadError,
    JsonSalesRepository,
    SalesRepository,
)
from .metrics import recurrent_customers, top_products, total_by_region
from .validator import ValidationError, validate


logger = logging.getLogger(__name__)
CURRENCY_DECIMALS = 2


def run(repository: SalesRepository, output_path: Path) -> None:
    """Procesa cualquier repositorio que cumpla el contrato de lectura."""
    # La lógica de procesamiento es la misma para CSV y JSON.
    sales = repository.load()
    valid_sales, invalid_sales = validate(sales)
    regional_totals = total_by_region(valid_sales)
    product_ranking = top_products(valid_sales)
    repeat_customers = recurrent_customers(valid_sales)

    # Guardamos solo las filas válidas; el JSON resume la calidad del conjunto.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    valid_sales.to_csv(output_path, index=False)
    quality = {
        "filas_totales": len(sales),
        "filas_validas": len(valid_sales),
        "filas_invalidas": len(invalid_sales),
        "importe_total": round(float(valid_sales["importe"].sum()), CURRENCY_DECIMALS),
    }
    quality_path = output_path.parent / "calidad_datos.json"
    with quality_path.open("w", encoding="utf-8") as file:
        json.dump(quality, file, indent=2, ensure_ascii=False)

    logger.info("Filas válidas: %s | inválidas: %s", len(valid_sales), len(invalid_sales))
    logger.info("Importe por región:\n%s", regional_totals.to_string())
    logger.info("Top productos:\n%s", product_ranking.to_string())
    logger.info("Clientes recurrentes:\n%s", repeat_customers.to_string())
    logger.info("Ventas guardadas en: %s", output_path)
    logger.info("Informe guardado en: %s", quality_path)


def main() -> int:
    """Devuelve 0 si termina bien y 1 si hay un error de datos o archivos."""
    parser = argparse.ArgumentParser(description="Valida ventas y calcula sus métricas.")
    parser.add_argument("--input", type=Path, required=True, help="CSV de entrada.")
    parser.add_argument("--output", type=Path, required=True, help="CSV de ventas limpias.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        # La selección del formato queda fuera de run (inyección de dependencia).
        repository: SalesRepository
        if args.input.suffix.lower() == ".json":
            repository = JsonSalesRepository(args.input)
        elif args.input.suffix.lower() == ".csv":
            repository = CsvSalesRepository(args.input)
        else:
            raise DataLoadError("El archivo de entrada debe ser CSV o JSON.")
        run(repository, args.output)
    except (DataLoadError, ValidationError, OSError) as error:
        logger.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    # Permite que la terminal detecte si la ejecución ha fallado.
    raise SystemExit(main())
