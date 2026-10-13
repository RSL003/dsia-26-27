"""Lectura de ventas desde CSV o JSON."""

import json
from pathlib import Path
from typing import Protocol

import pandas as pd


class DataLoadError(Exception):
    """No se ha podido leer el archivo de entrada."""


class SalesRepository(Protocol):
    """Contrato común: cargar devuelve un DataFrame o lanza DataLoadError."""

    def load(self) -> pd.DataFrame:
        ...


def load(path: Path) -> pd.DataFrame:
    """Lee un CSV y comunica los fallos mediante la excepción del ejercicio."""
    if not path.is_file():
        raise DataLoadError(f"No existe el archivo: {path}")
    try:
        return pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError) as error:
        # El resto del programa no necesita conocer los errores de pandas.
        raise DataLoadError(f"No se pudo leer el archivo: {path}") from error


class CsvSalesRepository:
    """Adapta la función de lectura CSV al contrato SalesRepository."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> pd.DataFrame:
        return load(self.path)


class JsonSalesRepository:
    """Lee una lista JSON de registros, uno por cada venta."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> pd.DataFrame:
        if not self.path.is_file():
            raise DataLoadError(f"No existe el archivo: {self.path}")
        try:
            with self.path.open(encoding="utf-8") as file:
                records = json.load(file)
        except (OSError, ValueError) as error:
            raise DataLoadError(
                f"No se pudo leer el JSON: {self.path}"
            ) from error

        # El enunciado exige una lista de records, no un objeto JSON suelto.
        if not isinstance(records, list) or not all(
            isinstance(record, dict) for record in records
        ):
            raise DataLoadError("El JSON debe contener una lista de registros.")

        # Las columnas y las reglas de negocio se comprueban en validator.py.
        return pd.DataFrame.from_records(records)
