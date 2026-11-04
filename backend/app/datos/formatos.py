"""Conversiones entre tipos de Python y columnas de SQLite.

Importes: Decimal <-> centavos (int). Fechas: datetime <-> texto ISO de ancho fijo.
"""

from datetime import datetime
from decimal import Decimal

from app.negocio.comunes import ZONA_HORARIA, redondear


def a_centavos(importe: Decimal) -> int:
    return int(redondear(Decimal(importe)) * 100)


def desde_centavos(centavos: int) -> Decimal:
    return (Decimal(centavos) / 100).quantize(Decimal("0.01"))


def fecha_a_texto(fecha: datetime) -> str:
    """Siempre en America/Buenos_Aires y con microsegundos, para poder comparar como texto."""
    return fecha.astimezone(ZONA_HORARIA).isoformat(timespec="microseconds")


def texto_a_fecha(texto: str) -> datetime:
    return datetime.fromisoformat(texto)


def a_bool(valor) -> bool | None:
    return None if valor is None else bool(valor)


def a_entero_bool(valor: bool | None) -> int | None:
    return None if valor is None else int(valor)
