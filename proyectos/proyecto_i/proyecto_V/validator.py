"""Reglas de calidad: separar registros válidos y rechazados sin imputar."""
import numpy as np
import pandas as pd

from .exceptions import EsquemaError

COLUMNAS = ["fecha", "region", "producto", "unidades", "precio_unitario", "cliente_id"]


class VentasValidator:
    """Valida tipos, rangos y campos obligatorios de cada venta."""

    def validar(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Devuelve válidos normalizados y errores con fila CSV y motivos."""
        faltantes = set(COLUMNAS) - set(frame.columns)
        if faltantes:
            raise EsquemaError(f"Faltan columnas: {', '.join(sorted(faltantes))}")
        datos = frame.copy().reset_index(drop=True)
        motivos = pd.Series("", index=datos.index, dtype=str)

        def marcar(mask: pd.Series, motivo: str) -> None:
            motivos.loc[mask] += motivo + "; "

        for campo in ("region", "producto", "cliente_id"):
            datos[campo] = datos[campo].astype("string").str.strip()
            marcar(datos[campo].isna() | datos[campo].eq(""), f"{campo}: obligatorio")
        marcar(~datos["region"].isin(["Norte", "Sur", "Este", "Oeste"]), "region: desconocida")
        formato_fecha = datos["fecha"].astype("string").str.fullmatch(r"\d{4}-\d{2}-\d{2}", na=False)
        fechas = pd.to_datetime(datos["fecha"], format="%Y-%m-%d", errors="coerce")
        marcar(fechas.isna() | ~formato_fecha, "fecha: debe ser una fecha válida YYYY-MM-DD")
        datos["fecha"] = fechas
        for campo in ("unidades", "precio_unitario"):
            numeros = pd.to_numeric(datos[campo], errors="coerce")
            incorrectos = numeros.isna() | ~np.isfinite(numeros) | numeros.le(0)
            marcar(incorrectos, f"{campo}: debe ser numérico, finito y > 0")
            if campo == "unidades":
                decimales = numeros.notna() & np.isfinite(numeros) & numeros.mod(1).ne(0)
                marcar(decimales, "unidades: debe ser entero")
                marcar(numeros.ge(2**63), "unidades: fuera del rango entero admitido")
            datos[campo] = numeros
        with np.errstate(over="ignore", invalid="ignore"):
            importes = (datos["unidades"].astype(float) * datos["precio_unitario"].astype(float)).round(2)
        marcar(~np.isfinite(importes), "importe: no se puede representar como número finito")
        # Sin ID de transacción, dos filas iguales podrían ser ventas legítimas.
        motivos = motivos.str.rstrip("; ")
        mask = motivos.ne("")
        errores = frame.reset_index(drop=True).loc[mask].copy()
        errores.insert(0, "fila_csv", errores.index + 2)
        errores["motivos"] = motivos.loc[mask]
        validos = datos.loc[~mask].copy()
        validos["unidades"] = validos["unidades"].astype("int64")
        validos["importe"] = importes.loc[~mask]
        return validos, errores
