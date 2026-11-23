"""Convierte las 24 columnas horarias en observaciones y las valida."""
import numpy as np
import pandas as pd
from .exceptions import AireError

IDENTIFICADORES = ["PROVINCIA", "MUNICIPIO", "ESTACION", "MAGNITUD", "PUNTO_MUESTREO"]


class AireValidator:
    """Separa observaciones utilizables y excluidas con sus motivos."""

    def validar(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Conserva el bloque horario H01–H24, sin inventar horas exactas."""
        requeridas = IDENTIFICADORES + ["ANO", "MES", "DIA"]
        for hora in range(1, 25):
            requeridas += [f"H{hora:02}", f"V{hora:02}"]
        faltantes = set(requeridas) - set(frame.columns)
        if faltantes:
            raise AireError(f"Faltan columnas: {sorted(faltantes)}")
        original = frame.reset_index(drop=True).copy()
        original["fecha"] = pd.to_datetime(
            original["ANO"] + "-" + original["MES"] + "-" + original["DIA"],
            format="%Y-%m-%d", errors="coerce",
        )
        original["fila_csv"] = original.index + 2
        for campo in IDENTIFICADORES:
            original[campo] = original[campo].fillna("").astype(str).str.strip()
        bloques = []
        for hora in range(1, 25):
            bloque = original[IDENTIFICADORES + ["fila_csv", "fecha"]].copy()
            bloque["valor_original"] = original[f"H{hora:02}"]
            bloque["estado"] = original[f"V{hora:02}"]
            bloque["hora"] = f"H{hora:02}"
            bloques.append(bloque)
        datos = pd.concat(bloques, ignore_index=True)
        datos = datos.sort_values(["fila_csv", "hora"]).reset_index(drop=True)
        datos["valor"] = pd.to_numeric(datos["valor_original"], errors="coerce")
        datos["motivos"] = ""

        def marcar(mask, mensaje):
            datos.loc[mask, "motivos"] += mensaje + "; "

        marcar(datos["fecha"].isna(), "fecha incorrecta")
        for campo in IDENTIFICADORES:
            marcar(datos[campo].eq(""), f"{campo} vacío")
        marcar(datos["estado"].ne("V"), "estado distinto de V: no se usa en métricas")
        incorrectos = datos["valor"].isna() | ~np.isfinite(datos["valor"]) | datos["valor"].lt(0)
        marcar(incorrectos, "valor no numérico, no finito o negativo")
        clave = ["PUNTO_MUESTREO", "fecha", "hora"]
        marcar(datos.duplicated(clave, keep=False), "clave horaria duplicada: revisar todas sus apariciones")
        datos["motivos"] = datos["motivos"].str.rstrip("; ")
        validos = datos.loc[datos["motivos"].eq("")].copy()
        errores = datos.loc[datos["motivos"].ne("")].copy()
        return validos, errores
