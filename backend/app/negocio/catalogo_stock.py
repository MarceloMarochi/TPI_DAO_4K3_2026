"""Catálogo compartido, existencias e ingresos simples al CD."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.negocio.comunes import redondear, validar_entero, validar_fecha, validar_importe_positivo, validar_positivo, validar_texto
from app.negocio.errores import Conflicto


class Producto:
    """Producto del catálogo. La categoría es un texto y el proveedor un código."""

    def __init__(self, codigo, nombre, categoria, proveedor_codigo, precio, costo_referencia):
        self._codigo = validar_texto(codigo, "codigo")
        self.nombre = nombre
        self.categoria = categoria
        self.proveedor_codigo = proveedor_codigo
        self.precio = precio
        self.costo_referencia = costo_referencia

    @property
    def codigo(self) -> str:
        return self._codigo

    @property
    def nombre(self) -> str:
        return self._nombre

    @nombre.setter
    def nombre(self, valor) -> None:
        self._nombre = validar_texto(valor, "nombre")

    @property
    def categoria(self) -> str:
        return self._categoria

    @categoria.setter
    def categoria(self, valor) -> None:
        self._categoria = validar_texto(valor, "categoria")

    @property
    def proveedor_codigo(self) -> str:
        return self._proveedor_codigo

    @proveedor_codigo.setter
    def proveedor_codigo(self, valor) -> None:
        self._proveedor_codigo = validar_texto(valor, "proveedor")

    @property
    def precio(self) -> Decimal:
        return self._precio

    @precio.setter
    def precio(self, valor) -> None:
        self._precio = validar_importe_positivo(valor, "precio")

    @property
    def costo_referencia(self) -> Decimal:
        """Último costo de compra informado; se copia en cada venta para el margen estimado."""
        return self._costo_referencia

    @costo_referencia.setter
    def costo_referencia(self, valor) -> None:
        self._costo_referencia = validar_importe_positivo(valor, "costo de referencia")

    def __eq__(self, otro) -> bool:
        return isinstance(otro, Producto) and otro.codigo == self._codigo

    def __hash__(self) -> int:
        return hash(self._codigo)

    def __repr__(self) -> str:
        return f"Producto({self._codigo!r}, {self._nombre!r})"


class Existencia:
    """Stock disponible y habilitado para la venta de un producto en un establecimiento.

    Lo comprometido, en tránsito o rechazado NO está acá: se consulta desde los bultos.
    El disponible sólo cambia con ingresar() y retirar(); el mínimo es editable.
    """

    def __init__(self, producto: Producto, cantidad: int = 0, minimo: int = 0):
        if not isinstance(producto, Producto):
            raise ValueError("producto: debe ser un Producto")
        self._producto = producto
        self._cantidad = validar_entero(cantidad, "cantidad")
        self.minimo = minimo

    @property
    def producto(self) -> Producto:
        return self._producto

    @property
    def cantidad(self) -> int:
        return self._cantidad

    @property
    def minimo(self) -> int:
        return self._minimo

    @minimo.setter
    def minimo(self, valor) -> None:
        self._minimo = validar_entero(valor, "minimo")

    def ingresar(self, cantidad: int) -> None:
        self._cantidad += validar_positivo(cantidad, "cantidad a ingresar")

    def retirar(self, cantidad: int) -> None:
        cantidad = validar_positivo(cantidad, "cantidad a retirar")
        if cantidad > self._cantidad:
            raise Conflicto(
                f"Stock insuficiente de {self._producto.codigo}: "
                f"disponible {self._cantidad}, solicitado {cantidad}"
            )
        self._cantidad -= cantidad

    def faltante(self) -> int:
        """Unidades que faltan para alcanzar el mínimo."""
        return max(0, self._minimo - self._cantidad)

    def bajo_minimo(self) -> bool:
        return self._cantidad < self._minimo

    def __repr__(self) -> str:
        return f"Existencia({self._producto.codigo!r}, cantidad={self._cantidad}, minimo={self._minimo})"


class Sucursal:
    """Establecimiento: el Centro de Distribución (es_cd=True) o un local.

    Contiene (composición) una existencia por producto.
    """

    def __init__(self, codigo, nombre, es_cd: bool = False):
        self._codigo = validar_texto(codigo, "codigo")
        self.nombre = nombre
        if not isinstance(es_cd, bool):
            raise ValueError("es_cd: debe ser verdadero o falso")
        self._es_cd = es_cd
        self._existencias: list[Existencia] = []

    @property
    def codigo(self) -> str:
        return self._codigo

    @property
    def nombre(self) -> str:
        return self._nombre

    @nombre.setter
    def nombre(self, valor) -> None:
        self._nombre = validar_texto(valor, "nombre")

    @property
    def es_cd(self) -> bool:
        return self._es_cd

    @property
    def existencias(self) -> list[Existencia]:
        return list(self._existencias)

    def buscar_existencia(self, codigo_producto: str) -> Existencia | None:
        for existencia in self._existencias:
            if existencia.producto.codigo == codigo_producto:
                return existencia
        return None

    def agregar_existencia(self, producto: Producto, cantidad: int = 0, minimo: int = 0) -> Existencia:
        """Crea la existencia del producto. `cantidad` distinta de cero sólo la usa el DAO al restaurar."""
        if self.buscar_existencia(producto.codigo) is not None:
            raise ValueError(f"{self._codigo} ya tiene existencia de {producto.codigo}")
        existencia = Existencia(producto, cantidad, minimo)
        self._existencias.append(existencia)
        return existencia

    def existencia_para(self, producto: Producto) -> Existencia:
        """Devuelve la existencia del producto, creándola en cero si no existe."""
        existencia = self.buscar_existencia(producto.codigo)
        if existencia is None:
            existencia = self.agregar_existencia(producto)
        return existencia

    def disponible(self, codigo_producto: str) -> int:
        existencia = self.buscar_existencia(codigo_producto)
        return existencia.cantidad if existencia else 0

    def __eq__(self, otro) -> bool:
        return isinstance(otro, Sucursal) and otro.codigo == self._codigo

    def __hash__(self) -> int:
        return hash(self._codigo)

    def __repr__(self) -> str:
        tipo = "CD" if self._es_cd else "Local"
        return f"Sucursal({self._codigo!r}, {tipo})"


class IngresoStock:
    """Entrada simple de compra al CD: un producto por registro."""

    def __init__(self, numero, producto: Producto, proveedor_codigo, cantidad, costo_unitario, fecha=None):
        self._numero = validar_texto(numero, "numero")
        if not isinstance(producto, Producto):
            raise ValueError("producto: debe ser un Producto")
        self._producto = producto
        self._proveedor_codigo = validar_texto(proveedor_codigo, "proveedor")
        self._cantidad = validar_positivo(cantidad, "cantidad")
        self._costo_unitario = validar_importe_positivo(costo_unitario, "costo unitario")
        self._fecha = validar_fecha(fecha)

    @property
    def numero(self) -> str:
        return self._numero

    @property
    def fecha(self) -> datetime:
        return self._fecha

    @property
    def producto(self) -> Producto:
        return self._producto

    @property
    def proveedor_codigo(self) -> str:
        return self._proveedor_codigo

    @property
    def cantidad(self) -> int:
        return self._cantidad

    @property
    def costo_unitario(self) -> Decimal:
        return self._costo_unitario

    def importe(self) -> Decimal:
        return redondear(self._costo_unitario * self._cantidad)

    def aplicar(self, cd: Sucursal) -> None:
        """Suma el stock al CD y actualiza el costo de referencia para ventas futuras."""
        if not cd.es_cd:
            raise ValueError("Los ingresos de compra sólo se registran en el Centro de Distribución")
        cd.existencia_para(self._producto).ingresar(self._cantidad)
        self._producto.costo_referencia = self._costo_unitario


def _validar_sucursal(valor, campo: str) -> Sucursal:
    if not isinstance(valor, Sucursal):
        raise ValueError(f"{campo}: debe ser una Sucursal")
    return valor


def _validar_producto(valor) -> Producto:
    if not isinstance(valor, Producto):
        raise ValueError("producto: debe ser un Producto")
    return valor
