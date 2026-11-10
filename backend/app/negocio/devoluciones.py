"""Devolución de una línea de venta y su reintegro histórico."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.negocio.comunes import a_decimal, redondear, validar_entero, validar_fecha, validar_positivo, validar_texto
from app.negocio.errores import Conflicto
from app.negocio.ventas import Venta, DetalleVenta


class Devolucion:
    """Devolución de una línea de una venta confirmada. Reintegra por el medio original."""

    def __init__(self, numero, venta: Venta, detalle: DetalleVenta, cantidad: int,
                 apta_reventa: bool, motivo, fecha=None):
        self._numero = validar_texto(numero, "numero")
        if not isinstance(venta, Venta) or not venta.confirmada:
            raise ValueError("Sólo se aceptan devoluciones de ventas registradas")
        if not venta.contiene(detalle):
            raise ValueError("La línea indicada no pertenece a la venta")
        self._venta = venta
        self._detalle = detalle
        self._cantidad = validar_positivo(cantidad, "cantidad")
        if not isinstance(apta_reventa, bool):
            raise ValueError("apta_reventa: debe indicarse si la mercadería es apta para la venta")
        self._apta_reventa = apta_reventa
        self._motivo = validar_texto(motivo, "motivo")
        self._fecha = validar_fecha(fecha)
        self._importe_reintegrado: Decimal | None = None

    @classmethod
    def restaurar(cls, numero, venta, detalle, cantidad, apta_reventa, motivo, fecha,
                  importe_reintegrado) -> Devolucion:
        devolucion = cls(numero, venta, detalle, cantidad, apta_reventa, motivo, fecha)
        devolucion._importe_reintegrado = redondear(Decimal(importe_reintegrado))
        return devolucion

    @property
    def numero(self) -> str:
        return self._numero

    @property
    def fecha(self) -> datetime:
        return self._fecha

    @property
    def venta(self) -> Venta:
        return self._venta

    @property
    def detalle(self) -> DetalleVenta:
        return self._detalle

    @property
    def cantidad(self) -> int:
        return self._cantidad

    @property
    def apta_reventa(self) -> bool:
        return self._apta_reventa

    @property
    def motivo(self) -> str:
        return self._motivo

    @property
    def medio_codigo(self) -> str:
        """El reintegro se hace por el medio de pago original de la venta."""
        return self._venta.medio_codigo

    @property
    def importe_reintegrado(self) -> Decimal | None:
        return self._importe_reintegrado

    @property
    def confirmada(self) -> bool:
        return self._importe_reintegrado is not None

    def validar(self, cantidad_ya_devuelta: int) -> None:
        """La cantidad acumulada devuelta no puede superar la vendida."""
        ya_devuelta = validar_entero(cantidad_ya_devuelta, "cantidad ya devuelta")
        if ya_devuelta + self._cantidad > self._detalle.cantidad:
            restante = max(0, self._detalle.cantidad - ya_devuelta)
            raise Conflicto(
                f"Se vendieron {self._detalle.cantidad} unidades y ya se devolvieron {ya_devuelta}: "
                f"sólo se pueden devolver {restante}"
            )

    def calcular_reintegro(self, importe_ya_devuelto, cantidad_ya_devuelta: int) -> Decimal:
        """Reintegro sobre el objetivo acumulado, conservando devoluciones históricas."""
        self.validar(cantidad_ya_devuelta)
        importe_ya_devuelto = redondear(a_decimal(importe_ya_devuelto, "importe ya devuelto"))
        cobrado = self._detalle.importe_cobrado
        if not Decimal("0") <= importe_ya_devuelto <= cobrado:
            raise Conflicto("El reintegro acumulado no puede superar lo cobrado en la línea")
        acumulada = cantidad_ya_devuelta + self._cantidad
        objetivo = (cobrado if acumulada == self._detalle.cantidad else
                    redondear(cobrado * acumulada / self._detalle.cantidad))
        # El algoritmo anterior pudo adelantar centavos: no se altera ese historial
        # ni se cobra al cliente; las siguientes devoluciones compensan la diferencia.
        return max(Decimal("0.00"), objetivo - importe_ya_devuelto)

    def confirmar(self, cantidad_ya_devuelta: int, importe_ya_devuelto) -> None:
        """Valida, fija el reintegro y, si la mercadería es apta, la devuelve al disponible del local."""
        if self.confirmada:
            raise Conflicto(f"La devolución {self._numero} ya fue registrada")
        self.validar(cantidad_ya_devuelta)
        self._importe_reintegrado = self.calcular_reintegro(importe_ya_devuelto, cantidad_ya_devuelta)
        if self._apta_reventa:
            self._venta.local.existencia_para(self._detalle.producto).ingresar(self._cantidad)

    def __repr__(self) -> str:
        return f"Devolucion({self._numero!r}, venta={self._venta.numero!r}, cantidad={self._cantidad})"
