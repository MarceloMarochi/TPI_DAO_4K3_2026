"""Necesidades de los locales consolidadas en órdenes de reposición."""
from __future__ import annotations

from datetime import datetime

from app.negocio.comunes import validar_entero, validar_fecha, validar_positivo, validar_texto
from app.negocio.errores import Conflicto
from app.negocio.catalogo_stock import Producto, Sucursal, _validar_producto, _validar_sucursal
from app.negocio.base_modelos import _ConId


class DetalleReposicion(_ConId):
    """Necesidad de un local: producto y cantidad a enviar desde el CD."""

    def __init__(self, destino: Sucursal, producto: Producto, cantidad: int, id: int | None = None):
        destino = _validar_sucursal(destino, "destino")
        if destino.es_cd:
            raise ValueError("El destino de una reposición debe ser un local, no el CD")
        self._destino = destino
        self._producto = _validar_producto(producto)
        self._cantidad = validar_positivo(cantidad, "cantidad")
        self._id = None
        if id is not None:
            self.asignar_id(id)

    @property
    def destino(self) -> Sucursal:
        return self._destino

    @property
    def producto(self) -> Producto:
        return self._producto

    @property
    def cantidad(self) -> int:
        return self._cantidad

    def sumar(self, cantidad: int) -> None:
        """Consolida otra necesidad del mismo producto y destino (lo invoca la orden)."""
        self._cantidad += validar_positivo(cantidad, "cantidad")

    def pendiente(self, asignado: int) -> int:
        """Cantidad que falta preparar, dado lo ya asignado a bultos."""
        return max(0, self._cantidad - validar_entero(asignado, "asignado"))

    def __repr__(self) -> str:
        return f"DetalleReposicion({self._destino.codigo!r}, {self._producto.codigo!r}, {self._cantidad})"


class OrdenReposicion:
    """Consolida directamente las necesidades de los locales; origen siempre el CD."""

    def __init__(self, numero, origen: Sucursal, fecha=None):
        self._numero = validar_texto(numero, "numero")
        origen = _validar_sucursal(origen, "origen")
        if not origen.es_cd:
            raise ValueError("El origen de una orden de reposición debe ser el CD")
        self._origen = origen
        self._fecha = validar_fecha(fecha)
        self._detalles: list[DetalleReposicion] = []
        self._cerrada = False

    @classmethod
    def restaurar(cls, numero, origen, fecha, detalles: list[DetalleReposicion], cerrada: bool) -> OrdenReposicion:
        orden = cls(numero, origen, fecha)
        orden._detalles = list(detalles)
        orden._cerrada = bool(cerrada)
        return orden

    @property
    def numero(self) -> str:
        return self._numero

    @property
    def fecha(self) -> datetime:
        return self._fecha

    @property
    def origen(self) -> Sucursal:
        return self._origen

    @property
    def detalles(self) -> list[DetalleReposicion]:
        return list(self._detalles)

    @property
    def cerrada(self) -> bool:
        return self._cerrada

    def agregar_necesidad(self, destino: Sucursal, producto: Producto, cantidad: int) -> DetalleReposicion:
        """Agrega una línea; si ya existe el mismo producto para el mismo destino, suma la cantidad."""
        if self._cerrada:
            raise Conflicto(f"La orden {self._numero} ya está en preparación y no admite cambios")
        for detalle in self._detalles:
            if detalle.destino == destino and detalle.producto == producto:
                detalle.sumar(cantidad)
                return detalle
        detalle = DetalleReposicion(destino, producto, cantidad)
        self._detalles.append(detalle)
        return detalle

    def contiene(self, detalle: DetalleReposicion) -> bool:
        return any(propio is detalle for propio in self._detalles)

    def buscar_detalle(self, id_detalle: int) -> DetalleReposicion | None:
        for detalle in self._detalles:
            if detalle.id == id_detalle:
                return detalle
        return None

    def validar(self) -> None:
        if not self._detalles:
            raise ValueError("La orden debe tener al menos una necesidad")

    def cerrar_edicion(self) -> None:
        """Congela las necesidades. Se invoca al preparar el primer bulto."""
        self.validar()
        self._cerrada = True

    def __repr__(self) -> str:
        return f"OrdenReposicion({self._numero!r}, detalles={len(self._detalles)})"
