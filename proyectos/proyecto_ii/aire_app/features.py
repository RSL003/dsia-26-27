"""Ejemplos de un paso horario, sin cruzar huecos ni usar meteorología futura."""
from __future__ import annotations

import numpy as np
import pandas as pd

BASE_FEATURES = ["valor_actual", "valor_anterior", "media_3_bloques",
                 "hora_sin", "hora_cos", "semana_sin", "semana_cos"]
WEATHER_FEATURES = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m",
                    "viento_sin", "viento_cos", "precipitation"]


def construir_variables(serie: pd.DataFrame, con_meteorologia: bool) -> pd.DataFrame:
    """Una sola serie; reindexa a horas UTC, sin rellenar valores ausentes.

    El origen t usa valores de t, t-1 y t-2 y predice el objetivo t+1.
    Las variables calendario son conocidas para el bloque objetivo.
    """
    raw = serie.copy()
    if raw.empty:
        raise ValueError("La serie está vacía")
    for col in ["estacion_id", "MAGNITUD"]:
        if col in raw and raw[col].nunique() != 1:
            raise ValueError("Se necesita una sola estación y magnitud")
    raw["timestamp_utc"] = pd.to_datetime(raw.timestamp_utc, utc=True)
    raw = raw.dropna(subset=["timestamp_utc"]).sort_values("timestamp_utc")
    if raw.empty or raw.timestamp_utc.duplicated().any():
        raise ValueError("Serie sin tiempos válidos o con duplicados")
    raw = raw.set_index("timestamp_utc")
    grid = pd.date_range(raw.index.min(), raw.index.max(), freq="h")
    raw = raw.reindex(grid)
    result = pd.DataFrame(index=grid)
    result["origen_utc"] = grid
    result["objetivo_utc"] = grid + pd.Timedelta(hours=1)
    result["valor_actual"] = raw.valor
    result["valor_anterior"] = raw.valor.shift(1)
    result["media_3_bloques"] = raw.valor.rolling(3, min_periods=3).mean()
    # Restar un instante identifica H24 con el día/bloque que termina, no H00.
    local = (grid + pd.Timedelta(hours=1) - pd.Timedelta(nanoseconds=1)).tz_convert("Europe/Madrid")
    bloque = local.hour + 1
    result["hora_sin"] = np.sin(2 * np.pi * bloque / 24)
    result["hora_cos"] = np.cos(2 * np.pi * bloque / 24)
    result["semana_sin"] = np.sin(2 * np.pi * local.dayofweek / 7)
    result["semana_cos"] = np.cos(2 * np.pi * local.dayofweek / 7)
    if con_meteorologia:
        for col in ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "precipitation"]:
            result[col] = raw[col].astype(float)
        direccion = np.deg2rad(raw.wind_direction_10m.astype(float))
        result["viento_sin"] = np.sin(direccion)
        result["viento_cos"] = np.cos(direccion)
    return result


def construir_ejemplos(serie: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Añade el objetivo observado a las variables compartidas con inferencia."""
    result = construir_variables(serie, con_meteorologia=True)
    result["objetivo"] = result.valor_actual.shift(-1)
    required = BASE_FEATURES + WEATHER_FEATURES + ["objetivo"]
    complete = np.isfinite(result[required]).all(axis=1)
    info = {"filas_serie": len(serie), "horas_rejilla": len(result),
            "ejemplos_completos": int(complete.sum()),
            "horas_sin_ejemplo_completo": int((~complete).sum())}
    # Mismas filas para ambos conjuntos de variables: comparación emparejada.
    return result.loc[complete].reset_index(drop=True), info


def dividir_temporal(frame: pd.DataFrame, validacion="2026-01-01", test="2026-05-01"):
    """Cortes por objetivo con un bloque de embargo en cada frontera."""
    v, t = pd.Timestamp(validacion, tz="UTC"), pd.Timestamp(test, tz="UTC")
    if v >= t:
        raise ValueError("Validación debe preceder al test")
    train = frame.loc[frame.objetivo_utc < v].copy()
    val = frame.loc[(frame.origen_utc >= v) & (frame.objetivo_utc < t)].copy()
    test_frame = frame.loc[frame.origen_utc >= t].copy()
    if min(len(train), len(val), len(test_frame)) < 100:
        raise ValueError("Se necesitan al menos 100 ejemplos en cada partición")
    return train, val, test_frame
