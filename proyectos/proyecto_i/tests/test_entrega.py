"""Comprobaciones independientes de procedencia y métricas de los datos reales."""
import hashlib
import json
from pathlib import Path
import pandas as pd
import pytest
from proyecto_M.cli import main as aire
from proyecto_V.cli import main as ventas

BASE = Path(__file__).resolve().parents[1]


def test_hash_datos_aire():
    origen = json.loads((BASE / "datos/internet/origen.json").read_text())
    assert hashlib.sha256((BASE / "datos/internet/aire.csv").read_bytes()).hexdigest() == origen["sha256"]


def test_metricas_ventas_con_datos_reales(tmp_path):
    assert ventas(["--output", str(tmp_path)]) == 0
    resumen = json.loads((tmp_path / "calidad_datos.json").read_text())
    assert resumen["importe_total"] == pytest.approx(96598.17)
    assert resumen["unidades_totales"] == 1816
    assert list(resumen["top_3_productos"]) == ["Gateway", "Hub IoT", "Sensor B"]


def test_medias_aire_con_calculo_independiente(tmp_path):
    assert aire(["--output", str(tmp_path)]) == 0
    resumen = json.loads((tmp_path / "resumen.json").read_text())
    original = pd.read_csv(BASE / "datos/internet/aire.csv", sep=";", dtype=str)
    for grupo in resumen["por_estacion_y_magnitud"]:
        filas = original.loc[(original["ESTACION"] == grupo["ESTACION"]) & (original["MAGNITUD"] == grupo["MAGNITUD"])]
        valores = []
        for hora in range(1, 25):
            seleccion = filas.loc[filas[f"V{hora:02}"].eq("V"), f"H{hora:02}"]
            valores.extend(float(v) for v in seleccion if float(v) >= 0)
        assert grupo["count"] == len(valores)
        assert grupo["mean"] == pytest.approx(round(sum(valores) / len(valores), 3))
        assert grupo["max"] == max(valores)


@pytest.mark.parametrize("modulo", ["proyecto_V", "proyecto_M"])
def test_modulo_devuelve_error_sin_traceback(modulo, tmp_path):
    import subprocess
    import sys
    proceso = subprocess.run(
        [sys.executable, "-m", modulo, "--input", str(tmp_path / "ausente.csv")],
        cwd=BASE, capture_output=True, text=True,
    )
    assert proceso.returncode == 1
    assert "Error:" in proceso.stderr
    assert "Traceback" not in proceso.stderr


def test_descarga_y_manifiesto_sin_red(tmp_path, monkeypatch):
    import importlib.util
    from io import BytesIO
    spec = importlib.util.spec_from_file_location("descarga_madrid", BASE / "datos/internet/madrid.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    contenido = (BASE / "datos/internet/aire.csv").read_bytes()
    monkeypatch.setattr(modulo, "__file__", str(tmp_path / "madrid.py"))
    monkeypatch.setattr(modulo, "urlopen", lambda url, timeout: BytesIO(contenido))
    modulo.descargar()
    assert (tmp_path / "aire.csv").read_bytes() == contenido
    manifiesto = json.loads((tmp_path / "origen.json").read_text())
    assert manifiesto["sha256"] == hashlib.sha256(contenido).hexdigest()
    monkeypatch.setattr(modulo, "urlopen", lambda url, timeout: BytesIO(b"<html>error</html>"))
    with pytest.raises(ValueError):
        modulo.descargar()
    assert (tmp_path / "aire.csv").read_bytes() == contenido
