"""Coordina las etapas del análisis de calidad del aire."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from tempfile import mkdtemp

import pandas as pd

from .ai_client import InformeError, generar_informe
from .download_air import descargar
from .enrich import construir_base_validada
from .loader import AireLoader
from .metrics import calcular_metricas
from .predict import predecir
from .validator import AireValidator


def ejecutar_pipeline(entrada: Path, salida: Path) -> tuple[int, int, int]:
    """Carga, valida y exporta los datos; devuelve los recuentos de filas."""
    filas, validos, excluidas = analizar_csv(entrada, salida)
    return filas, len(validos), excluidas


def analizar_csv(entrada: Path, salida: Path) -> tuple[int, pd.DataFrame, int]:
    """Exporta la auditoría y devuelve las observaciones que pueden entrar en SQLite."""
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
    return len(frame), validos, len(errores)


def ejecutar_completo(datos: Path, salida: Path, actualizar: bool, modo_ia: str) -> Path:
    """Ejecuta todas las etapas en una carpeta propia y devuelve su ruta."""
    from .compare_modelos import comparar

    logger = logging.getLogger(__name__)
    salida.mkdir(parents=True, exist_ok=True)
    ejecucion = Path(mkdtemp(prefix="aire-", dir=salida.resolve()))
    logger.info("Directorio de esta ejecución: %s", ejecucion)
    if actualizar:
        logger.info("Descargando el CSV actual del Ayuntamiento de Madrid")
        entrada = descargar(ejecucion / "datos")
        cache = ejecucion / "datos/meteo_cache"
    else:
        entrada = datos / "reproduccion/aire_plaza_espana.csv"
        cache = datos / "reproduccion/era5"

    filas, validos, excluidas = analizar_csv(entrada, ejecucion / "calidad")
    logger.info("CSV de %s filas: %s observaciones válidas y %s excluidas", filas, len(validos), excluidas)
    database = ejecucion / "aire.sqlite"
    logger.info("Construyendo SQLite con las observaciones validadas y ERA5")
    construir_base_validada(validos, excluidas, entrada, datos / "estaciones.csv",
                            cache, database, offline=not actualizar)
    modelos = ejecucion / "modelos"
    logger.info("Entrenando y evaluando los candidatos para NO₂ en Plaza de España")
    comparar(database, ejecucion / "comparacion", modelos)
    ejecutar_inferencia(database, modelos, ejecucion / "inferencia", modo_ia)
    return ejecucion


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
