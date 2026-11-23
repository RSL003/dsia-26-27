"""Pruebas con datos locales y errores representativos."""
import json
from pathlib import Path
import pytest
from proyecto_M.loader import AireLoader
from proyecto_M.validator import AireValidator
from proyecto_M.cli import main
from proyecto_M.exceptions import AireError

DATOS = Path(__file__).resolve().parents[1] / "datos/internet/aire.csv"


def test_datos_reales():
    frame = AireLoader().cargar(DATOS)
    validos, errores = AireValidator().validar(frame)
    assert len(validos) + len(errores) == len(frame) * 24
    assert len(validos) > 0
    assert validos["estado"].eq("V").all()
    assert validos["valor"].ge(0).all()


def test_cero_valido_y_cero_sin_dato():
    frame = AireLoader().cargar(DATOS).head(1).copy()
    frame.loc[0, ["H01", "V01", "H02", "V02"]] = ["0", "V", "0", "N"]
    validos, errores = AireValidator().validar(frame)
    assert "H01" in validos["hora"].values
    assert "H02" in errores["hora"].values


@pytest.mark.parametrize("campo,valor", [("H01", "abc"), ("H01", "inf"), ("H01", "-1"), ("ANO", "nada"), ("ESTACION", "")])
def test_rechazos(campo, valor):
    frame = AireLoader().cargar(DATOS).head(1).copy()
    frame.loc[0, campo] = valor
    validos, errores = AireValidator().validar(frame)
    assert "H01" not in validos["hora"].values
    assert "H01" in errores["hora"].values


def test_duplicados_y_esquema():
    frame = AireLoader().cargar(DATOS).head(2).copy()
    frame.iloc[1] = frame.iloc[0]
    validos, errores = AireValidator().validar(frame)
    assert validos.empty
    assert errores["motivos"].str.contains("duplicada").all()
    with pytest.raises(AireError):
        AireValidator().validar(frame.drop(columns="H24"))


def test_cli(tmp_path):
    assert main(["--input", str(DATOS), "--output", str(tmp_path)]) == 0
    resumen = json.loads((tmp_path / "resumen.json").read_text())
    assert resumen["observaciones_horarias"] == resumen["filas_originales"] * 24
    assert (tmp_path / "aire_limpio.csv").exists()
    assert main(["--input", str(tmp_path / "ausente")]) == 1


def test_identificador_nulo():
    frame = AireLoader().cargar(DATOS).head(1).copy()
    frame.loc[0, "ESTACION"] = None
    validos, errores = AireValidator().validar(frame)
    assert validos.empty
    assert errores["motivos"].str.contains("ESTACION vacío").all()


def test_csv_con_campos_de_mas(tmp_path):
    ruta = tmp_path / "mal.csv"
    ruta.write_text("PROVINCIA;MUNICIPIO\n28;079;EXTRA\n")
    with pytest.raises(AireError):
        AireLoader().cargar(ruta)


def test_entrada_sin_filas_y_sin_validos(tmp_path):
    frame = AireLoader().cargar(DATOS)
    sin_validos = frame.head(1).copy()
    for hora in range(1, 25):
        sin_validos[f"V{hora:02}"] = "N"
    for nombre, ejemplo in [("vacio", frame.head(0)), ("sin_validos", sin_validos)]:
        ruta = tmp_path / f"{nombre}.csv"
        ejemplo.to_csv(ruta, sep=";", index=False)
        salida = tmp_path / nombre
        assert main(["--input", str(ruta), "--output", str(salida)]) == 0
        resumen = json.loads((salida / "resumen.json").read_text())
        assert resumen["observaciones_utilizables"] == 0
        assert resumen["por_estacion_y_magnitud"] == []
