"""Lectura del CSV municipal."""
from pathlib import Path
import warnings
import pandas as pd
from .exceptions import AireError


class AireLoader:
    """Lee los datos originales como texto, conservando códigos y ceros."""

    def cargar(self, ruta: Path) -> pd.DataFrame:
        """Carga un CSV separado por punto y coma."""
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", pd.errors.ParserWarning)
                return pd.read_csv(ruta, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False, index_col=False)
        except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError, pd.errors.ParserWarning) as exc:
            raise AireError(f"No se pudo leer {ruta}: {exc}") from exc
