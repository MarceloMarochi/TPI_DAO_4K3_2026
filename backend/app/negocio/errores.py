"""Errores de negocio.

Todos heredan de ValueError (como pide el diseño), pero permiten a la API
responder con el código HTTP adecuado:

    ValueError común  -> 422  dato inválido (precio negativo, texto vacío, ...)
    NoEncontrado      -> 404  el código o número no existe
    Conflicto         -> 409  regla incumplida según el estado actual:
                              stock insuficiente, transición no permitida,
                              duplicado, documento ya confirmado, cotización vencida
"""


class NoEncontrado(ValueError):
    pass


class Conflicto(ValueError):
    pass


class ErrorImportacion(ValueError):
    """El archivo CSV tiene errores. No se importó ninguna fila."""

    def __init__(self, errores: list[dict]):
        self.errores = errores
        super().__init__(f"El archivo tiene {len(errores)} error(es); no se importó ninguna fila")
