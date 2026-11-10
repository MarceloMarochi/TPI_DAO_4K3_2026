"""Conversión de entradas de CSV y errores por fila."""

def _a_entero(valor, campo: str) -> int:
    """Acepta enteros o texto numérico (los CSV llegan como texto)."""
    if isinstance(valor, str):
        try:
            valor = int(valor.strip())
        except ValueError:
            raise ValueError(f"{campo}: debe ser un número entero") from None
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ValueError(f"{campo}: debe ser un número entero")
    return valor


def _a_bool(valor, campo: str) -> bool:
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        texto = valor.strip().lower()
        if texto in ("si", "sí", "s", "true", "verdadero", "1", "x"):
            return True
        if texto in ("no", "n", "false", "falso", "0", ""):
            return False
    raise ValueError(f"{campo}: debe ser sí o no")


def _error_de_fila(numero_fila: int, error: Exception) -> dict:
    mensaje = str(error)
    campo = None
    # Convención de los mensajes de validación: "campo: descripción" (en minúscula).
    if ":" in mensaje and mensaje[:1].islower():
        campo = mensaje.split(":", 1)[0]
    return {"fila": numero_fila, "campo": campo, "mensaje": mensaje}
