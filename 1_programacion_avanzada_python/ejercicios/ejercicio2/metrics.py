"""Métricas sobre ventas validadas; no lee ni escribe archivos."""

import pandas as pd


TOP_PRODUCTS_LIMIT = 3
MIN_PURCHASES_FOR_RECURRENT_CUSTOMER = 2


def total_by_region(sales: pd.DataFrame) -> pd.Series:
    """Suma el importe por región y ordena de mayor a menor."""
    return sales.groupby("region")["importe"].sum().sort_values(ascending=False)


def top_products(
    sales: pd.DataFrame, limit: int = TOP_PRODUCTS_LIMIT
) -> pd.Series:
    """Selecciona los productos con mayor importe total, no más unidades."""
    return (
        sales.groupby("producto")["importe"]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
    )


def recurrent_customers(sales: pd.DataFrame) -> pd.Series:
    """Cuenta filas de venta por cliente, igual que en el ejercicio anterior."""
    purchases = sales.groupby("cliente_id").size()
    return purchases[
        purchases >= MIN_PURCHASES_FOR_RECURRENT_CUSTOMER
    ].sort_values(ascending=False)
