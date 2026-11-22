"""API y dashboard del Proyecto III sobre el núcleo del Proyecto II."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3

from flask import Flask, jsonify, render_template
from pandas.errors import DatabaseError

from .ai_client import generar_informe
from .exceptions import AireError
from .predict import cargar_candidato, predecir

BASE = Path(__file__).resolve().parents[1]
ERRORES_DATOS = (AireError, OSError, ValueError, KeyError, TypeError, sqlite3.Error, DatabaseError)


def create_app(database=None, modelos=None):
    app = Flask(__name__)
    app.logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    database = Path(database or os.getenv("AIRE_DATABASE", BASE / "datos/aire_meteo.sqlite"))
    modelos = Path(modelos or os.getenv("AIRE_MODELS", BASE / "modelos"))

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.get("/health")
    def health():
        try:
            metadata, _ = cargar_candidato(modelos)
            with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
                hay_datos = conn.execute(
                    "SELECT 1 FROM aire_enriquecido WHERE estacion_id = ? AND MAGNITUD = ? "
                    "AND timestamp_utc IS NOT NULL LIMIT 1",
                    (metadata["estacion"], metadata["magnitud"]),
                ).fetchone()
            if not hay_datos:
                raise AireError("La serie configurada no tiene datos horarios")
        except ERRORES_DATOS as exc:
            app.logger.warning("Servicio no preparado: %s", exc)
            return jsonify(estado="no_disponible"), 503
        return jsonify(estado="disponible", modelo=metadata["seleccionado"])

    @app.post("/predict")
    def predict():
        try:
            resultado = predecir(database, modelos)
        except ERRORES_DATOS as exc:
            app.logger.warning("No se pudo predecir: %s", exc)
            return jsonify(error="No se pudo predecir con la base y el modelo configurados."), 503
        app.logger.info("Modelo %s, objetivo %s", resultado["modelo"], resultado["objetivo_utc"])
        return jsonify(prediccion=resultado, informe=generar_informe(resultado, "mock"), modo_ia="mock")

    return app
