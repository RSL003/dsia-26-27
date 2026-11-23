"""Verifica el contrato temporal, no solo la forma de la tabla."""
import numpy as np
import pandas as pd
import pytest

from aire_app.features import BASE_FEATURES, WEATHER_FEATURES, construir_ejemplos, dividir_temporal


def serie(horas=10):
    tiempo = pd.date_range("2025-01-01", periods=horas, freq="h", tz="UTC")
    return pd.DataFrame({"timestamp_utc": tiempo, "valor": np.arange(horas, dtype=float),
                         "temperature_2m": 15., "relative_humidity_2m": 60.,
                         "wind_speed_10m": 2., "wind_direction_10m": 359.,
                         "precipitation": 0., "estacion_id": "28079004", "MAGNITUD": "8"})


def test_valores_conocidos_y_meteo_no_futura():
    raw = serie()
    raw["temperature_2m"] = np.arange(10) + 10
    frame, _ = construir_ejemplos(raw)
    row = frame.iloc[0]
    assert (row.valor_actual, row.valor_anterior, row.media_3_bloques, row.objetivo) == (2, 1, 1, 3)
    assert row.temperature_2m == 12  # t, nunca temperatura t+1=13
    futuro = raw.copy()
    futuro.loc[3:, "valor"] += 1000
    futuro.loc[3:, "temperature_2m"] += 1000
    modificado, _ = construir_ejemplos(futuro)
    np.testing.assert_allclose(frame.iloc[0][BASE_FEATURES + WEATHER_FEATURES].astype(float),
                               modificado.iloc[0][BASE_FEATURES + WEATHER_FEATURES].astype(float))
    assert modificado.iloc[0].objetivo != row.objetivo


def test_huecos_no_se_comprimen():
    raw = serie().drop(index=4)
    frame, _ = construir_ejemplos(raw)
    horas = frame.origen_utc.dt.hour.tolist()
    assert horas == [2, 7, 8]


def test_no_mezcla_series_ni_duplicados():
    raw = serie()
    raw.loc[0, "MAGNITUD"] = "10"
    with pytest.raises(ValueError, match="una sola"):
        construir_ejemplos(raw)
    raw = pd.concat([serie(), serie().head(1)])
    with pytest.raises(ValueError, match="duplicados"):
        construir_ejemplos(raw)


def test_fronteras_temporales_sin_objetivos_adelantados():
    raw = serie(1000)
    frame, _ = construir_ejemplos(raw)
    train, val, test = dividir_temporal(frame, "2025-01-15", "2025-01-29")
    assert train.objetivo_utc.max() < val.origen_utc.min()
    assert val.objetivo_utc.max() < test.origen_utc.min()
    assert set(train.index).isdisjoint(val.index)
    assert set(val.index).isdisjoint(test.index)


def test_calendario_ciclico_y_h24():
    raw = serie(30)
    frame, _ = construir_ejemplos(raw)
    # Objetivo UTC 23h de invierno = fin local 24h del mismo día.
    row = frame.loc[frame.objetivo_utc.dt.hour.eq(23)].iloc[0]
    assert row.hora_sin == pytest.approx(0, abs=1e-12)
    assert row.hora_cos == pytest.approx(1)
    assert row.viento_cos > .99  # 359° queda próximo a 0°
