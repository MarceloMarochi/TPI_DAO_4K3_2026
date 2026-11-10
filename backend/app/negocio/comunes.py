"""Funciones auxiliares compartidas por las clases del negocio.

Validaciones de datos simples, manejo de importes con Decimal y fecha del servidor.
Todas las validaciones lanzan ValueError con un mensaje legible.
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

ZONA_HORARIA = ZoneInfo("America/Buenos_Aires")
CENTAVOS = Decimal("0.01")


def ahora() -> datetime:
    """Fecha y hora del servidor, con zona horaria."""
    return datetime.now(ZONA_HORARIA)


def redondear(importe: Decimal) -> Decimal:
    """Redondea un importe a centavos (mitad hacia arriba)."""
    return importe.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def a_decimal(valor, campo: str) -> Decimal:
    """Convierte int, str o Decimal a Decimal. Los float pasan por str para no arrastrar error binario."""
    if isinstance(valor, bool):
        raise ValueError(f"{campo}: debe ser un número")
    if isinstance(valor, float):
        valor = str(valor)
    try:
        resultado = Decimal(valor)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{campo}: debe ser un número") from None
    if not resultado.is_finite():
        raise ValueError(f"{campo}: debe ser un número finito")
    return resultado


def validar_texto(valor, campo: str) -> str:
    """Texto no vacío, sin espacios sobrantes en los extremos."""
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{campo}: no puede estar vacío")
    return valor.strip()


def validar_entero(valor, campo: str, minimo: int = 0) -> int:
    """Entero mayor o igual a `minimo`."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ValueError(f"{campo}: debe ser un número entero")
    if valor < minimo:
        raise ValueError(f"{campo}: debe ser mayor o igual a {minimo}")
    return valor


def validar_positivo(valor, campo: str) -> int:
    """Entero estrictamente positivo."""
    return validar_entero(valor, campo, minimo=1)


def validar_importe_positivo(valor, campo: str) -> Decimal:
    """Importe mayor que cero, redondeado a centavos."""
    importe = a_decimal(valor, campo)
    if importe <= 0:
        raise ValueError(f"{campo}: debe ser mayor que cero")
    return redondear(importe)


def validar_total_esperado(valor) -> Decimal:
    """Importe obligatorio, finito, no negativo y representable en centavos."""
    if valor is None:
        raise ValueError("total_esperado: es obligatorio; cotice antes de confirmar")
    importe = a_decimal(valor, "total_esperado")
    try:
        centavos = redondear(importe)
    except InvalidOperation:
        raise ValueError("total_esperado: importe fuera de rango") from None
    if importe < 0 or importe != centavos:
        raise ValueError("total_esperado: debe ser no negativo y tener como máximo dos decimales")
    return centavos


def validar_fecha(valor, campo: str = "fecha") -> datetime:
    """Fecha con zona horaria; si no se informa, se usa la del servidor."""
    if valor is None:
        return ahora()
    if not isinstance(valor, datetime) or valor.tzinfo is None:
        raise ValueError(f"{campo}: debe ser una fecha con zona horaria")
    return valor
