"""Comprueba calidad del dataset, reglas y ejecución completa."""
import json
from pathlib import Path

import pandas as pd
import pytest

from proyecto_V.cli import main
from proyecto_V.exceptions import CargaError, EsquemaError
from proyecto_V.loader import VentasLoader
from proyecto_V.metrics import calcular_metricas
from proyecto_V.validator import VentasValidator

DATOS = Path(__file__).resolve().parents[1] / "datos/ventas/ventas.csv"


def test_dataset_curso():
    frame = VentasLoader().cargar(DATOS)
    validos, errores = VentasValidator().validar(frame)
    assert (len(frame), len(validos), len(errores)) == (150, 140, 10)
    assert set(validos.index).isdisjoint(errores.index)
    assert errores["motivos"].str.len().gt(0).all()
    resumen = calcular_metricas(validos, len(frame))
    assert sum(resumen["importe_por_region"].values()) == pytest.approx(resumen["importe_total"])


@pytest.mark.parametrize("campo,valor", [("unidades", "1.5"), ("unidades", "inf"), ("precio_unitario", "-1"), ("fecha", "2026-02-30"), ("region", " "), ("cliente_id", "")])
def test_rechaza_reglas(campo, valor):
    frame = VentasLoader().cargar(DATOS).head(1)
    frame.loc[0, campo] = valor
    validos, errores = VentasValidator().validar(frame)
    assert validos.empty
    assert len(errores) == 1


def test_errores_de_dominio(tmp_path):
    with pytest.raises(CargaError):
        VentasLoader().cargar(tmp_path / "no_existe.csv")
    with pytest.raises(EsquemaError):
        VentasValidator().validar(pd.DataFrame({"otra": [1]}))


def test_cli_exporta(tmp_path):
    assert main(["--input", str(DATOS), "--output", str(tmp_path)]) == 0
    assert len(pd.read_csv(tmp_path / "ventas_limpias.csv")) == 140
    assert len(pd.read_csv(tmp_path / "ventas_rechazadas.csv")) == 10
    assert json.loads((tmp_path / "calidad_datos.json").read_text())["filas_invalidas"] == 10
    assert main(["--input", str(tmp_path / "ausente.csv")]) == 1


@pytest.mark.parametrize("campo,valor", [
    ("unidades", "100000000000000000000"),
    ("precio_unitario", "1e308"),
    ("fecha", "2026-1-9"),
])
def test_limites_y_formato_fecha(campo, valor):
    frame = VentasLoader().cargar(DATOS).head(1).copy()
    frame.loc[0, campo] = valor
    validos, errores = VentasValidator().validar(frame)
    assert validos.empty
    assert len(errores) == 1


def test_csv_con_campos_de_mas(tmp_path):
    ruta = tmp_path / "mal.csv"
    ruta.write_text("fecha,region,producto,unidades,precio_unitario,cliente_id\n2026-01-09,Sur,Cable,7,12.5,C005,EXTRA\n")
    with pytest.raises(CargaError):
        VentasLoader().cargar(ruta)


def test_entrada_sin_filas_y_sin_validos(tmp_path):
    frame = VentasLoader().cargar(DATOS)
    for nombre, ejemplo in [("vacio", frame.head(0)), ("sin_validos", frame.head(1).assign(unidades="-1"))]:
        ruta = tmp_path / f"{nombre}.csv"
        ejemplo.to_csv(ruta, index=False)
        salida = tmp_path / nombre
        assert main(["--input", str(ruta), "--output", str(salida)]) == 0
        resumen = json.loads((salida / "calidad_datos.json").read_text())
        assert resumen["filas_validas"] == 0
        assert resumen["importe_total"] == 0
