"""Resultados conocidos, calculados a mano, e integración de la CLI."""
import json
from pathlib import Path

import pytest

from aire_app.cli import main
from aire_app.loader import AireLoader
from aire_app.metrics import calcular_metricas
from aire_app.validator import AireValidator

MUESTRA = Path(__file__).parent / "fixtures/aire_muestra.csv"


def ejemplo_controlado():
    """Dos valores válidos y 22 bloques sin dato en una fila municipal."""
    frame = AireLoader().cargar(MUESTRA)
    for hora in range(1, 25):
        frame[f"V{hora:02}"] = "N"
    frame.loc[0, ["H01", "V01", "H02", "V02"]] = ["10", "V", "30", "V"]
    return frame


def test_metricas_con_resultados_conocidos():
    validos, errores = AireValidator().validar(ejemplo_controlado())
    resumen = calcular_metricas(validos, errores, 1)
    assert resumen["observaciones_horarias"] == 24
    assert resumen["observaciones_utilizables"] == 2
    assert resumen["observaciones_excluidas"] == 22
    assert resumen["porcentaje_utilizables"] == pytest.approx(8.33)
    assert resumen["estaciones_con_datos"] == 1
    grupo, = resumen["por_estacion_y_magnitud"]
    assert (grupo["count"], grupo["mean"], grupo["max"]) == (2, 20, 30)
    assert [g["mean"] for g in resumen["por_magnitud_y_hora"]] == [10, 30]


def test_integracion_exporta_valores_y_motivos(tmp_path):
    entrada = tmp_path / "entrada.csv"
    ejemplo_controlado().to_csv(entrada, sep=";", index=False)
    salida = tmp_path / "salida"
    assert main(["--input", str(entrada), "--output", str(salida)]) == 0
    resumen = json.loads((salida / "resumen.json").read_text())
    assert resumen["observaciones_utilizables"] == 2
    import pandas as pd
    limpios = pd.read_csv(salida / "aire_limpio.csv")
    excluidos = pd.read_csv(salida / "aire_excluido.csv")
    assert limpios["valor"].tolist() == [10, 30]
    assert len(excluidos) == 22
    assert excluidos["motivos"].str.contains("estado distinto de V").all()
