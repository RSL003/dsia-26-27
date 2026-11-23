"""Inferencia de un bloque horario con el candidato elegido en validación."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import pickle
import sqlite3
from typing import TypedDict

import joblib
import numpy as np
import pandas as pd

from .exceptions import AireError
from .features import BASE_FEATURES, WEATHER_FEATURES, construir_variables


class Prediccion(TypedDict):
    """Resultado compartido por la CLI, la API y el cliente de informes."""

    modelo: str
    archivo_modelo: str | None
    estacion_id: str
    estacion: str
    magnitud: str
    unidad: str
    origen_utc: str
    objetivo_utc: str
    ultimo_valor_observado: float
    valor_predicho: float
    horizonte_horas: int
    meteorologia_era5: bool
    sklearn: str | None
    entrenado_hasta_objetivo_utc: str | None
    evaluacion: dict[str, float]


def cargar_candidato(modelos: Path) -> tuple[dict, dict]:
    metadata = json.loads((modelos / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("horizonte_horas") != 1:
        raise AireError("El horizonte del candidato debe ser de una hora")
    nombre = metadata["seleccionado"]
    archivo = metadata["archivo"]
    if nombre == "persistencia" and archivo is None:
        return metadata, {"features": ["valor_actual"]}
    if archivo != f"{nombre}.joblib" or Path(archivo).name != archivo:
        raise AireError("El archivo del candidato en metadata.json no es válido")
    try:
        modelo = joblib.load(modelos / archivo)
    except (OSError, ValueError, EOFError, ImportError, AttributeError, pickle.UnpicklingError) as exc:
        raise AireError(f"No se pudo cargar {archivo}: {exc}") from exc
    columnas = modelo.get("features") if isinstance(modelo, dict) else None
    if columnas not in (BASE_FEATURES, BASE_FEATURES + WEATHER_FEATURES):
        raise AireError("El contrato de variables del candidato no es compatible")
    if (modelo.get("estacion_id") != metadata["estacion"]
            or modelo.get("magnitud") != metadata["magnitud"]
            or modelo.get("horizonte_horas") != 1):
        raise AireError("El candidato no coincide con la serie o el horizonte de sus metadatos")
    estimador = modelo.get("estimator")
    if (not callable(getattr(estimador, "predict", None))
            or list(getattr(estimador, "feature_names_in_", columnas)) != columnas):
        raise AireError("El estimador no coincide con el contrato de variables")
    return metadata, modelo


def predecir(database: Path, modelos: Path) -> Prediccion:
    """Predice desde el último bloque resoluble de la serie del candidato."""
    metadata, modelo = cargar_candidato(modelos)
    estacion, magnitud = metadata["estacion"], metadata["magnitud"]
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as con:
        serie = pd.read_sql_query(
            "SELECT * FROM aire_enriquecido WHERE estacion_id = ? AND MAGNITUD = ?",
            con, params=(estacion, magnitud),
        )
    if serie.empty:
        raise AireError(f"No hay datos para la estación {estacion} y la magnitud {magnitud}")
    columnas = modelo["features"]
    usa_meteorologia = columnas == BASE_FEATURES + WEATHER_FEATURES
    ultimo = construir_variables(serie, usa_meteorologia).iloc[[-1]]
    entradas = ultimo[columnas]
    if not np.isfinite(entradas.to_numpy()).all():
        raise AireError("El último bloque no tiene historial consecutivo o meteorología suficiente")
    observado = float(ultimo.valor_actual.iat[0])
    estimador = modelo.get("estimator")
    valor = observado if estimador is None else float(estimador.predict(entradas)[0])
    if not np.isfinite(valor):
        raise AireError("El candidato devolvió una predicción no finita")
    return {
        "modelo": metadata["seleccionado"], "archivo_modelo": metadata["archivo"],
        "estacion_id": estacion, "estacion": str(serie.nombre_estacion.iat[0]),
        "magnitud": magnitud, "unidad": "µg/m³" if magnitud == "8" else "ver catálogo",
        "origen_utc": ultimo.origen_utc.iat[0].isoformat(),
        "objetivo_utc": ultimo.objetivo_utc.iat[0].isoformat(),
        "ultimo_valor_observado": observado, "valor_predicho": valor,
        "horizonte_horas": 1, "meteorologia_era5": usa_meteorologia,
        "sklearn": modelo.get("sklearn"),
        "entrenado_hasta_objetivo_utc": modelo.get("entrenado_hasta_objetivo_utc"),
        "evaluacion": modelo.get("evaluacion", {}),
    }
