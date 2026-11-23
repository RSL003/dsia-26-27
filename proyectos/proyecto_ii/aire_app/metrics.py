"""Agregaciones sin mezclar magnitudes de distintas unidades."""
import pandas as pd


def calcular_metricas(validos: pd.DataFrame, errores: pd.DataFrame, filas: int) -> dict:
    """Calcula recuentos, medias, máximos y medias por bloque horario."""
    por_estacion = validos.groupby(["ESTACION", "MAGNITUD"])["valor"].agg(["count", "mean", "max"]).round(3).reset_index()
    por_hora = validos.groupby(["MAGNITUD", "hora"])["valor"].agg(["count", "mean"]).round(3).reset_index()
    total = len(validos) + len(errores)
    return {
        "filas_originales": filas,
        "observaciones_horarias": total,
        "observaciones_utilizables": len(validos),
        "observaciones_excluidas": len(errores),
        "porcentaje_utilizables": round(100 * len(validos) / total, 2) if total else 0,
        "estaciones_con_datos": int(validos["ESTACION"].nunique()),
        "estados_excluidos": {str(k): int(v) for k, v in errores["estado"].value_counts().items()},
        "por_estacion_y_magnitud": por_estacion.to_dict(orient="records"),
        "por_magnitud_y_hora": por_hora.to_dict(orient="records"),
    }
