"""Ejecuta la CLI con SQLite y un modelo sklearn persistido."""
from contextlib import closing
import json
import sqlite3
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from aire_app import ai_client
from aire_app.cli import main
from aire_app.features import BASE_FEATURES, WEATHER_FEATURES
from aire_app.web import create_app


@pytest.mark.parametrize("meteorologia", [False, True])
def test_cli_inferencia_sin_objetivo_futuro(tmp_path, meteorologia, capsys, monkeypatch):
    monkeypatch.setenv("AIRE_AI_MODE", "mock")
    database = tmp_path / "aire.sqlite"
    modelos = tmp_path / "modelos"
    salida = tmp_path / "salida"
    modelos.mkdir()
    serie = pd.DataFrame({
        "timestamp_utc": pd.date_range("2026-08-01", periods=4, freq="h", tz="UTC"),
        "valor": [7., 8., 9., 10.], "estacion_id": "28079004",
        "MAGNITUD": "8", "nombre_estacion": "Plaza de España",
    })
    columnas = BASE_FEATURES.copy()
    if meteorologia:
        columnas += WEATHER_FEATURES
        serie = serie.assign(temperature_2m=20., relative_humidity_2m=60.,
                             wind_speed_10m=2., wind_direction_10m=90., precipitation=0.)
    with closing(sqlite3.connect(database)) as con:
        serie.to_sql("aire_enriquecido", con, index=False)
    datos = pd.DataFrame(np.random.default_rng(42).normal(size=(30, len(columnas))), columns=columnas)
    estimador = LinearRegression().fit(datos, datos.valor_actual + 2)
    nombre = "ols_meteorologia" if meteorologia else "ols_base"
    archivo = f"{nombre}.joblib"
    metadata = {"seleccionado": nombre, "archivo": archivo, "estacion": "28079004",
                "magnitud": "8", "horizonte_horas": 1}
    (modelos / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    joblib.dump({"estimator": estimador, "features": columnas, "estacion_id": "28079004",
                 "magnitud": "8", "horizonte_horas": 1}, modelos / archivo)

    argumentos = ["run", "--database", str(database), "--models", str(modelos), "--output", str(salida)]
    assert main(argumentos) == 0
    resultado = json.loads((salida / "prediccion.json").read_text(encoding="utf-8"))
    assert resultado["modelo"] == nombre
    assert resultado["origen_utc"] == "2026-08-01T03:00:00+00:00"
    assert resultado["objetivo_utc"] == "2026-08-01T04:00:00+00:00"
    assert resultado["valor_predicho"] == pytest.approx(12)
    assert resultado["meteorologia_era5"] is meteorologia
    informe = salida / "informe.md"
    assert "(mock)" in informe.read_text(encoding="utf-8")

    cliente = create_app(database, modelos).test_client()
    assert cliente.get("/").status_code == 200
    assert b'fetch("/predict"' in cliente.get("/static/dashboard.js").data
    assert cliente.get("/health").get_json()["modelo"] == nombre
    respuesta_web = cliente.post("/predict")
    assert respuesta_web.status_code == 200
    assert respuesta_web.get_json()["prediccion"] == resultado
    assert respuesta_web.get_json()["modo_ia"] == "mock"

    if meteorologia:
        monkeypatch.delenv("HF_TOKEN", raising=False)
        assert main([*argumentos, "--ai-mode", "real"]) == 1
        assert "Configura HF_TOKEN" in capsys.readouterr().err
        monkeypatch.setenv("HF_TOKEN", "hf_prueba")
        monkeypatch.setenv("HF_MODEL", "organizacion/modelo-prueba")

        class ClienteHF:
            def __init__(self, *, model, provider, token, timeout):
                assert (model, provider, token, timeout) == (
                    "organizacion/modelo-prueba", "auto", "hf_prueba", 15,
                )

            def chat_completion(self, mensajes, *, max_tokens):
                assert max_tokens == 300
                assert mensajes[0]["role"] == "system"
                assert json.loads(mensajes[1]["content"]) == resultado
                mensaje = SimpleNamespace(content="Informe de prueba")
                return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)])

        monkeypatch.setattr(ai_client, "InferenceClient", ClienteHF)
        assert main([*argumentos, "--ai-mode", "real"]) == 0
        texto = informe.read_text(encoding="utf-8")
        assert "Hugging Face · organizacion/modelo-prueba" in texto
        assert "Informe de prueba" in texto
        monkeypatch.setenv("AIRE_AI_MODE", "real")
        cliente_real = create_app(database, modelos).test_client()
        assert cliente_real.post("/predict").get_json() == {
            "modo_ia": "real", "informe": texto, "prediccion": resultado,
        }

        def fallo(self, mensajes, *, max_tokens):
            raise ai_client.InferenceTimeoutError("timeout de prueba")

        monkeypatch.setattr(ClienteHF, "chat_completion", fallo)
        assert main([*argumentos, "--ai-mode", "real"]) == 1
        assert "La predicción está en" in capsys.readouterr().err
        assert json.loads((salida / "prediccion.json").read_text(encoding="utf-8")) == resultado
        assert "Informe no disponible" in informe.read_text(encoding="utf-8")
        parcial = cliente_real.post("/predict")
        assert parcial.status_code == 200
        assert parcial.get_json()["informe"] is None
        assert parcial.get_json()["prediccion"] == resultado
        assert "Hugging Face" in parcial.get_json()["aviso"]

    with closing(sqlite3.connect(database)) as con, con:
        con.execute("DELETE FROM aire_enriquecido WHERE substr(timestamp_utc, 12, 2) = '02'")
    assert main(argumentos) == 1
    assert "historial consecutivo" in capsys.readouterr().err
    assert cliente.post("/predict").status_code == 503
