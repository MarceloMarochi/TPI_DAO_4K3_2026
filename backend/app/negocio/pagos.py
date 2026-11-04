"""Patrón Strategy: cálculo del total según el medio de pago.

Venta es el contexto: invoca medio.calcular_total(subtotal) sin saber qué medio es.
Para agregar un medio nuevo se crea otra subclase y se registra en MEDIOS_PAGO.
"""

from abc import ABC, abstractmethod
from decimal import Decimal

from app.negocio.comunes import a_decimal, redondear, validar_texto


class MedioPago(ABC):
    """Estrategia abstracta de cobro."""

    def __init__(self, codigo: str):
        self._codigo = validar_texto(codigo, "codigo del medio de pago")

    @property
    def codigo(self) -> str:
        return self._codigo

    @property
    @abstractmethod
    def tasa(self) -> Decimal:
        """Tasa que se aplica (descuento o recargo). La venta la guarda como dato histórico."""

    @abstractmethod
    def calcular_total(self, base: Decimal) -> Decimal:
        """Total a cobrar a partir del subtotal de la venta."""

    @staticmethod
    def _validar_base(base) -> Decimal:
        base = a_decimal(base, "base")
        if base < 0:
            raise ValueError("base: no puede ser negativa")
        return base

    def __repr__(self) -> str:
        return f"{type(self).__name__}(tasa={self.tasa})"


class Efectivo(MedioPago):
    """Aplica un descuento: total = base × (1 − descuento), con 0 ≤ descuento < 1."""

    CODIGO = "EFECTIVO"

    def __init__(self, descuento):
        super().__init__(self.CODIGO)
        descuento = a_decimal(descuento, "descuento")
        if not Decimal("0") <= descuento < Decimal("1"):
            raise ValueError("descuento: debe estar entre 0 (inclusive) y 1 (exclusive)")
        self._descuento = descuento

    @property
    def descuento(self) -> Decimal:
        return self._descuento

    @property
    def tasa(self) -> Decimal:
        return self._descuento

    def calcular_total(self, base) -> Decimal:
        base = self._validar_base(base)
        return redondear(base * (Decimal("1") - self._descuento))


class Tarjeta(MedioPago):
    """Aplica un recargo: total = base × (1 + recargo), con recargo ≥ 0."""

    CODIGO = "TARJETA"

    def __init__(self, recargo):
        super().__init__(self.CODIGO)
        recargo = a_decimal(recargo, "recargo")
        if recargo < 0:
            raise ValueError("recargo: no puede ser negativo")
        self._recargo = recargo

    @property
    def recargo(self) -> Decimal:
        return self._recargo

    @property
    def tasa(self) -> Decimal:
        return self._recargo

    def calcular_total(self, base) -> Decimal:
        base = self._validar_base(base)
        return redondear(base * (Decimal("1") + self._recargo))


# Registro para reconstruir un medio a partir del código guardado en la base.
MEDIOS_PAGO: dict[str, type[MedioPago]] = {
    Efectivo.CODIGO: Efectivo,
    Tarjeta.CODIGO: Tarjeta,
}


def crear_medio_pago(codigo: str, tasa) -> MedioPago:
    """Crea la estrategia correspondiente a un código ('EFECTIVO' o 'TARJETA')."""
    clase = MEDIOS_PAGO.get(codigo)
    if clase is None:
        raise ValueError(f"medio de pago desconocido: {codigo}")
    return clase(tasa)
