"""Errores de dominio que la CLI puede presentar sin un traceback."""


class VentasError(Exception):
    """Error controlado del pipeline de ventas."""


class CargaError(VentasError):
    """El fichero no existe o no es un CSV legible."""


class EsquemaError(VentasError):
    """El CSV no contiene las columnas necesarias."""
