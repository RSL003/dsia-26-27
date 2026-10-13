"""Indicadores calculados exclusivamente sobre ventas válidas."""
import pandas as pd


def calcular_metricas(validos: pd.DataFrame, filas_totales: int) -> dict:
    """Resume calidad, facturación, unidades y clientes recurrentes."""
    def importes(campo: str) -> dict:
        serie = validos.groupby(campo)["importe"].sum().sort_values(ascending=False)
        return {str(k): round(float(v), 2) for k, v in serie.items()}

    productos = importes("producto")
    clientes = validos.groupby("cliente_id").size()
    mensual = validos.assign(mes=validos["fecha"].dt.strftime("%Y-%m")).groupby("mes")["importe"].sum()
    return {
        "filas_totales": filas_totales,
        "filas_validas": len(validos),
        "filas_invalidas": filas_totales - len(validos),
        "porcentaje_validas": round(100 * len(validos) / filas_totales, 2) if filas_totales else 0,
        "importe_total": round(float(validos["importe"].sum()), 2),
        "unidades_totales": sum(int(valor) for valor in validos["unidades"]),
        "importe_medio_por_registro": round(float(validos["importe"].mean()), 2) if len(validos) else 0,
        "importe_por_region": importes("region"),
        "importe_por_producto": productos,
        "top_3_productos": dict(list(productos.items())[:3]),
        "importe_por_mes": {k: round(float(v), 2) for k, v in mensual.items()},
        "clientes_recurrentes": {k: int(v) for k, v in clientes.items() if v > 1},
    }
