"""Reglas de validación de las ventas."""

import pandas as pd


class ValidationError(Exception):
    """Faltan datos estructurales necesarios para procesar las ventas."""


REQUIRED_COLUMNS = {
    "region", "producto", "cliente_id", "unidades", "precio_unitario"
}
MIN_UNITS = 0
MIN_UNIT_PRICE = 0


def validate(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve las filas válidas y las inválidas sin modificar la entrada."""
    # Sin estas columnas no se pueden aplicar las reglas ni las métricas.
    missing_columns = REQUIRED_COLUMNS - set(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValidationError(f"Faltan columnas: {missing}")

    sales = frame.copy()
    # Los valores que no se puedan convertir pasan a NaN y quedan rechazados.
    sales["unidades"] = pd.to_numeric(sales["unidades"], errors="coerce")
    sales["precio_unitario"] = pd.to_numeric(
        sales["precio_unitario"], errors="coerce"
    )
    valid_mask = (
        sales["unidades"].gt(MIN_UNITS)
        & sales["precio_unitario"].gt(MIN_UNIT_PRICE)
    )

    # Una fila incorrecta no impide aprovechar las demás ventas del archivo.
    valid_sales = sales.loc[valid_mask].copy()
    invalid_sales = sales.loc[~valid_mask].copy()
    valid_sales["importe"] = (
        valid_sales["unidades"] * valid_sales["precio_unitario"]
    )
    return valid_sales, invalid_sales
