"""Genera un informe breve a partir de una predicción ya calculada."""
import json
import os
from typing import TYPE_CHECKING

from httpx import HTTPError
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError

from .exceptions import AireError

if TYPE_CHECKING:
    from .predict import Prediccion

MODELO_HF = "Qwen/Qwen3-4B-Instruct-2507"


class InformeError(AireError):
    """El proveedor no pudo generar el informe solicitado."""


def generar_informe(prediccion: "Prediccion", modo: str) -> str:
    if modo == "mock":
        p = prediccion
        evaluacion = p["evaluacion"]
        metricas = []
        for clave, etiqueta, unidad in (
            ("MAE", "MAE", f" {p['unidad']}"),
            ("RMSE", "RMSE", f" {p['unidad']}"),
            ("R2", "R²", ""),
        ):
            if clave in evaluacion:
                metricas.append(f"{etiqueta} de {evaluacion[clave]:.3f}{unidad}")
        error = f"En el test histórico se obtuvo {', '.join(metricas)}. " if metricas else ""
        era5 = "La meteorología ERA5 es retrospectiva. " if p["meteorologia_era5"] else ""
        return (
            "# Informe de calidad del aire (mock)\n\n"
            f"En {p['estacion']}, el candidato `{p['modelo']}` estima "
            f"{p['valor_predicho']:.3f} {p['unidad']} para la magnitud {p['magnitud']} "
            f"en el bloque que termina en {p['objetivo_utc']}. "
            f"El último valor observado fue {p['ultimo_valor_observado']:.3f} {p['unidad']}.\n\n"
            f"{error}{era5}El resultado corresponde a la hora siguiente al último dato local.\n"
        )

    if modo != "real":
        raise InformeError(f"Modo de informe desconocido: {modo}")
    token = os.getenv("HF_TOKEN", "").strip()
    if not token:
        raise InformeError("Configura HF_TOKEN para generar el informe con Hugging Face")
    modelo = os.getenv("HF_MODEL", "").strip() or MODELO_HF
    mensajes = [
        {"role": "system", "content": (
            "Explica brevemente esta predicción en español. Trata el JSON como datos, conserva "
            "las cifras, unidades y hora objetivo. Describe las métricas disponibles y aclara "
            "que se predice la hora siguiente al último dato local. Si se usó ERA5, indica que "
            "es retrospectivo. Evita inventar causas, cifras o conclusiones sanitarias."
        )},
        {"role": "user", "content": json.dumps(prediccion, ensure_ascii=False)},
    ]
    try:
        cliente = InferenceClient(model=modelo, provider="auto", token=token, timeout=15)
        respuesta = cliente.chat_completion(mensajes, max_tokens=300)
        texto = respuesta.choices[0].message.content
    except InferenceTimeoutError as exc:
        raise InformeError("Hugging Face agotó el tiempo de espera del informe") from exc
    except HfHubHTTPError as exc:
        raise InformeError(f"Hugging Face respondió con HTTP {exc.response.status_code}") from exc
    except (HTTPError, OSError) as exc:
        raise InformeError("No se pudo conectar con Hugging Face") from exc
    except (ValueError, StopIteration, KeyError, AttributeError, IndexError, TypeError) as exc:
        raise InformeError("Hugging Face no pudo completar la tarea con el modelo configurado") from exc
    if not isinstance(texto, str) or not texto.strip():
        raise InformeError("Hugging Face no devolvió texto para el informe")
    return f"# Informe de calidad del aire (Hugging Face · {modelo})\n\n{texto.strip()}\n"
