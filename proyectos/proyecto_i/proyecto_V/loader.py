"""Lectura del fichero de entrada sin modificar los datos originales."""
from pathlib import Path
import warnings

import pandas as pd

from .exceptions import CargaError


class VentasLoader:
    """Carga ventas como texto para conservar los valores rechazados."""

    def cargar(self, ruta: Path) -> pd.DataFrame:
        """Lee un CSV UTF-8; traduce errores de lectura a errores de dominio."""
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", pd.errors.ParserWarning)
                return pd.read_csv(ruta, dtype=str, keep_default_na=False, index_col=False)
        except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError, pd.errors.ParserWarning) as exc:
            raise CargaError(f"No se pudo leer {ruta}: {exc}") from exc
