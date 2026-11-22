"""Coordina las etapas del análisis de calidad del aire."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .ai_client import InformeError, generar_informe
from .loader import AireLoader
from .metrics import calcular_metricas
from .predict import predecir
from .validator import AireValidator


def ejecutar_pipeline(entrada: Path, salida: Path) -> tuple[int, int, int]:
    """Carga, valida y exporta los datos; devuelve los recuentos de filas."""
    logger = logging.getLogger(__name__)
    logger.info("Leyendo el CSV municipal de %s", entrada)
    frame = AireLoader().cargar(entrada)
    validos, errores = AireValidator().validar(frame)
    resumen = calcular_metricas(validos, errores, len(frame))
    contenido = json.dumps(resumen, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    salida.mkdir(parents=True, exist_ok=True)
    validos.to_csv(salida / "aire_limpio.csv", index=False, date_format="%Y-%m-%d")
    errores.to_csv(salida / "aire_excluido.csv", index=False, date_format="%Y-%m-%d")
    (salida / "resumen.json").write_text(contenido, encoding="utf-8")
    logger.info("Análisis de calidad guardado en %s", salida)
    return len(frame), len(validos), len(errores)


def ejecutar_inferencia(database: Path, modelos: Path, salida: Path, modo_ia: str = "mock") -> Path:
    """Exporta la predicción antes de solicitar el informe."""
    logger = logging.getLogger(__name__)
    logger.info("Preparando la inferencia desde %s", database)
    resultado = predecir(database, modelos)
    salida.mkdir(parents=True, exist_ok=True)
    destino = salida / "prediccion.json"
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                       encoding="utf-8")
    logger.info("Predicción de %s para %s guardada en %s",
                resultado["modelo"], resultado["objetivo_utc"], destino)
    informe = salida / "informe.md"
    try:
        texto = generar_informe(resultado, modo_ia)
    except InformeError as exc:
        informe.write_text(f"# Informe no disponible\n\n{exc}\n", encoding="utf-8")
        raise InformeError(f"{exc}. La predicción está en {destino}") from exc
    informe.write_text(texto, encoding="utf-8")
    logger.info("Informe en modo %s guardado en %s", modo_ia, informe)
    return destino
