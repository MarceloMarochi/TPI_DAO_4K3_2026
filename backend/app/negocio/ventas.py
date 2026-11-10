"""Ventas con precios históricos y distribución del cobro por línea."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.negocio.comunes import a_decimal, redondear, validar_fecha, validar_importe_positivo, validar_positivo, validar_texto
from app.negocio.errores import Conflicto
from app.negocio.catalogo_stock import Producto, Sucursal, _validar_producto, _validar_sucursal
from app.negocio.base_modelos import _ConId
from app.negocio.pagos import MedioPago


class DetalleVenta(_ConId):
    """Línea de venta con precio y costo históricos."""

    def __init__(self, producto: Producto, cantidad: int, precio_unitario, costo_unitario,
                 id: int | None = None, importe_cobrado=None):
        self._producto = _validar_producto(producto)
        self._cantidad = validar_positivo(cantidad, "cantidad")
        self._precio_unitario = validar_importe_positivo(precio_unitario, "precio unitario")
        self._costo_unitario = validar_importe_positivo(costo_unitario, "costo unitario")
        self._importe_cobrado: Decimal | None = None
        self._id = None
        if id is not None:
            self.asignar_id(id)
        if importe_cobrado is not None:
            self.asignar_importe(importe_cobrado)

    @property
    def producto(self) -> Producto:
        return self._producto

    @property
    def cantidad(self) -> int:
        return self._cantidad

    @property
    def precio_unitario(self) -> Decimal:
        return self._precio_unitario

    @property
    def costo_unitario(self) -> Decimal:
        return self._costo_unitario

    @property
    def importe_cobrado(self) -> Decimal | None:
        """Parte del total cobrado que corresponde a esta línea (incluye descuento o recargo)."""
        return self._importe_cobrado

    def sumar(self, cantidad: int) -> None:
        if self._importe_cobrado is not None:
            raise ValueError("No se puede modificar una línea de una venta confirmada")
        self._cantidad += validar_positivo(cantidad, "cantidad")

    def asignar_importe(self, importe) -> None:
        if self._importe_cobrado is not None:
            raise ValueError("El importe cobrado de la línea ya fue asignado")
        importe = a_decimal(importe, "importe cobrado")
        if importe < 0:
            raise ValueError("importe cobrado: no puede ser negativo")
        self._importe_cobrado = redondear(importe)

    def subtotal(self) -> Decimal:
        return redondear(self._precio_unitario * self._cantidad)

    def costo_total(self) -> Decimal:
        return redondear(self._costo_unitario * self._cantidad)

    def margen(self) -> Decimal:
        if self._importe_cobrado is None:
            raise ValueError("El margen se calcula sobre una venta confirmada")
        return self._importe_cobrado - self.costo_total()

    def __repr__(self) -> str:
        return f"DetalleVenta({self._producto.codigo!r}, {self._cantidad})"


class Venta:
    """Contexto del patrón Strategy. Registra un único cobro y su comprobante interno."""

    def __init__(self, numero, local: Sucursal, medio: MedioPago, fecha=None):
        self._numero = validar_texto(numero, "numero")
        local = _validar_sucursal(local, "local")
        if local.es_cd:
            raise ValueError("Las ventas se registran en un local, no en el CD")
        self._local = local
        self._fecha = validar_fecha(fecha)
        self._detalles: list[DetalleVenta] = []
        self._confirmada = False
        self._total_cobrado: Decimal | None = None
        self._comprobante_numero: str | None = None
        self.medio = medio

    @classmethod
    def restaurar(cls, numero, local, medio: MedioPago, fecha, detalles: list[DetalleVenta],
                  total_cobrado, comprobante_numero) -> Venta:
        venta = cls(numero, local, medio, fecha)
        venta._detalles = list(detalles)
        venta._total_cobrado = redondear(Decimal(total_cobrado))
        venta._comprobante_numero = comprobante_numero
        venta._confirmada = True
        return venta

    # --- Propiedades ---

    @property
    def numero(self) -> str:
        return self._numero

    @property
    def fecha(self) -> datetime:
        return self._fecha

    @property
    def local(self) -> Sucursal:
        return self._local

    @property
    def detalles(self) -> list[DetalleVenta]:
        return list(self._detalles)

    @property
    def medio(self) -> MedioPago:
        return self._medio

    @medio.setter
    def medio(self, valor: MedioPago) -> None:
        self._exigir_borrador()
        if not isinstance(valor, MedioPago):
            raise ValueError("medio: debe ser un MedioPago")
        self._medio = valor

    @property
    def medio_codigo(self) -> str:
        return self._medio.codigo

    @property
    def tasa_aplicada(self) -> Decimal:
        return self._medio.tasa

    @property
    def total_cobrado(self) -> Decimal | None:
        return self._total_cobrado

    @property
    def comprobante_numero(self) -> str | None:
        return self._comprobante_numero

    @property
    def confirmada(self) -> bool:
        return self._confirmada

    # --- Operaciones ---

    def agregar_detalle(self, producto: Producto, cantidad: int) -> DetalleVenta:
        """Agrega un producto; si ya está en la venta, suma la cantidad. Copia precio y costo vigentes."""
        self._exigir_borrador()
        producto = _validar_producto(producto)
        cantidad = validar_positivo(cantidad, "cantidad")
        existente = self._buscar_linea(producto.codigo)
        total_pedido = cantidad + (existente.cantidad if existente else 0)
        disponible = self._local.disponible(producto.codigo)
        if total_pedido > disponible:
            raise Conflicto(
                f"Stock insuficiente de {producto.codigo} en {self._local.codigo}: "
                f"disponible {disponible}, solicitado {total_pedido}"
            )
        if existente:
            existente.sumar(cantidad)
            return existente
        detalle = DetalleVenta(producto, cantidad, producto.precio, producto.costo_referencia)
        self._detalles.append(detalle)
        return detalle

    def contiene(self, detalle: DetalleVenta) -> bool:
        return any(propio is detalle for propio in self._detalles)

    def buscar_detalle(self, id_detalle: int) -> DetalleVenta | None:
        for detalle in self._detalles:
            if detalle.id == id_detalle:
                return detalle
        return None

    def subtotal(self) -> Decimal:
        return sum((detalle.subtotal() for detalle in self._detalles), Decimal("0.00"))

    def calcular_total(self) -> Decimal:
        """Delegación en la estrategia: la venta no sabe qué medio de pago es."""
        return self._medio.calcular_total(self.subtotal())

    def ajuste(self) -> Decimal:
        """Diferencia entre total y subtotal: negativa si es descuento, positiva si es recargo."""
        return self.calcular_total() - self.subtotal()

    def confirmar(self, comprobante_numero: str | None = None) -> None:
        """Descuenta el stock del local, fija el total y lo distribuye entre las líneas."""
        self._exigir_borrador()
        if not self._detalles:
            raise ValueError("La venta debe tener al menos un producto")
        for detalle in self._detalles:
            disponible = self._local.disponible(detalle.producto.codigo)
            if detalle.cantidad > disponible:
                raise Conflicto(
                    f"Stock insuficiente de {detalle.producto.codigo} en {self._local.codigo}: "
                    f"disponible {disponible}, solicitado {detalle.cantidad}"
                )
        for detalle in self._detalles:
            self._local.buscar_existencia(detalle.producto.codigo).retirar(detalle.cantidad)

        total = self.calcular_total()
        self._distribuir_total(total)
        self._total_cobrado = total
        self._comprobante_numero = validar_texto(
            comprobante_numero or f"CI-{self._numero}", "numero de comprobante"
        )
        self._confirmada = True

    def _distribuir_total(self, total: Decimal) -> None:
        """Distribuye centavos por mayor resto, con desempate por código de producto.

        Los cocientes enteros evitan que la precisión decimal cambie el orden de
        los restos. Ninguna línea absorbe por sí sola los redondeos del resto.
        """
        total_centavos = int(total * 100)
        pesos = [int(detalle.subtotal() * 100) for detalle in self._detalles]
        base = sum(pesos)
        cuotas = [divmod(total_centavos * peso, base) for peso in pesos]
        importes = [cuota for cuota, _ in cuotas]
        pendientes = total_centavos - sum(importes)
        orden = sorted(range(len(cuotas)), key=lambda i: (
            -cuotas[i][1], self._detalles[i].producto.codigo,
        ))
        for i in orden[:pendientes]:
            importes[i] += 1
        for detalle, centavos in zip(self._detalles, importes):
            detalle.asignar_importe(Decimal(centavos) / 100)

    def _buscar_linea(self, codigo_producto: str) -> DetalleVenta | None:
        for detalle in self._detalles:
            if detalle.producto.codigo == codigo_producto:
                return detalle
        return None

    def _exigir_borrador(self) -> None:
        if getattr(self, "_confirmada", False):
            raise Conflicto(f"La venta {self._numero} está confirmada y no admite cambios")

    def __repr__(self) -> str:
        return f"Venta({self._numero!r}, local={self._local.codigo!r}, confirmada={self._confirmada})"
