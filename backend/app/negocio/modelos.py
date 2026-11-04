"""Clases de dominio del Sistema de Ventas e Inventario.

Convenciones (ver docs/Documento maestro del TP.md, sección 7):
- Atributos protegidos con prefijo _; acceso con @property.
- Los setters validan y lanzan ValueError.
- Las colecciones se devuelven como copias.
- Los datos históricos no se modifican después de confirmados.
- Los métodos `restaurar` reconstruyen objetos leídos de la base sin repetir
  efectos de negocio (descuentos de stock, historial, etc.). Sólo los usan los DAOs.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.negocio.comunes import (
    a_decimal,
    ahora,
    redondear,
    validar_entero,
    validar_fecha,
    validar_importe_positivo,
    validar_positivo,
    validar_texto,
)
from app.negocio.errores import Conflicto
from app.negocio.estados import EstadoBulto, Preparado
from app.negocio.pagos import MedioPago


# ---------------------------------------------------------------------------
# Catálogo y stock
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Reposición y bultos
# ---------------------------------------------------------------------------


def _validar_sucursal(valor, campo: str) -> Sucursal:
    if not isinstance(valor, Sucursal):
        raise ValueError(f"{campo}: debe ser una Sucursal")
    return valor


def _validar_producto(valor) -> Producto:
    if not isinstance(valor, Producto):
        raise ValueError("producto: debe ser un Producto")
    return valor


class _ConId:
    """Identificador numérico asignado por la base al guardar; se asigna una sola vez."""

    _id: int | None = None

    @property
    def id(self) -> int | None:
        return self._id

    def asignar_id(self, valor: int) -> None:
        if self._id is not None:
            raise ValueError("El identificador ya fue asignado")
        self._id = validar_positivo(valor, "id")


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


class DetalleBulto:
    """Cantidad de una línea de la orden que viaja en el bulto."""

    def __init__(self, pedido: DetalleReposicion, cantidad: int):
        if not isinstance(pedido, DetalleReposicion):
            raise ValueError("pedido: debe ser un DetalleReposicion")
        self._pedido = pedido
        self._cantidad = validar_positivo(cantidad, "cantidad")
        if self._cantidad > pedido.cantidad:
            raise Conflicto(
                f"No se pueden enviar {self._cantidad} unidades de {pedido.producto.codigo}: "
                f"se pidieron {pedido.cantidad}"
            )

    @property
    def pedido(self) -> DetalleReposicion:
        return self._pedido

    @property
    def producto(self) -> Producto:
        return self._pedido.producto

    @property
    def cantidad(self) -> int:
        return self._cantidad

    def __repr__(self) -> str:
        return f"DetalleBulto({self.producto.codigo!r}, {self._cantidad})"


class CambioEstado:
    """Registro inmutable de una transición del bulto. Una vez creado no se puede modificar."""

    def __init__(self, secuencia: int, fecha: datetime, anterior: str | None, nuevo: str, motivo: str = ""):
        self._secuencia = validar_positivo(secuencia, "secuencia")
        self._fecha = validar_fecha(fecha)
        self._anterior = anterior
        self._nuevo = validar_texto(nuevo, "estado nuevo")
        self._motivo = (motivo or "").strip()
        self._congelado = True

    def __setattr__(self, nombre, valor) -> None:
        if getattr(self, "_congelado", False):
            raise AttributeError("CambioEstado es inmutable")
        super().__setattr__(nombre, valor)

    def __delattr__(self, nombre) -> None:
        raise AttributeError("CambioEstado es inmutable")

    @property
    def secuencia(self) -> int:
        return self._secuencia

    @property
    def fecha(self) -> datetime:
        return self._fecha

    @property
    def anterior(self) -> str | None:
        return self._anterior

    @property
    def nuevo(self) -> str:
        return self._nuevo

    @property
    def motivo(self) -> str:
        return self._motivo

    def __repr__(self) -> str:
        return f"CambioEstado({self._secuencia}, {self._anterior} -> {self._nuevo})"


class Bulto:
    """Contexto del patrón State. Integra remito, precinto y recepción.

    Crear un bulto equivale a prepararlo: valida el contenido, cierra la orden y
    descuenta el disponible del CD una única vez. El contenido queda fijo.
    """

    def __init__(self, codigo, orden: OrdenReposicion, destino: Sucursal, remito_numero,
                 contenido: list[tuple[DetalleReposicion, int]], fecha=None):
        self._codigo = validar_texto(codigo, "codigo")
        self._remito_numero = validar_texto(remito_numero, "numero de remito")
        if not isinstance(orden, OrdenReposicion):
            raise ValueError("orden: debe ser una OrdenReposicion")
        destino = _validar_sucursal(destino, "destino")
        if destino.es_cd:
            raise ValueError("El destino de un bulto debe ser un local")
        self._orden = orden
        self._destino = destino
        self._detalles = self._armar_detalles(orden, destino, contenido)
        self._precinto_numero: str | None = None
        self._precinto_intacto: bool | None = None

        self._comprometer_origen()
        orden.cerrar_edicion()

        self._estado: EstadoBulto = Preparado()
        self._historial = [CambioEstado(1, validar_fecha(fecha), None, self._estado.nombre(), "Bulto preparado")]

    @staticmethod
    def _armar_detalles(orden, destino, contenido) -> list[DetalleBulto]:
        if not contenido:
            raise ValueError("El bulto debe tener contenido")
        detalles: list[DetalleBulto] = []
        for pedido, cantidad in contenido:
            if not orden.contiene(pedido):
                raise ValueError("Cada línea del bulto debe pertenecer a su orden de reposición")
            if pedido.destino != destino:
                raise ValueError(
                    f"La línea de {pedido.producto.codigo} es para {pedido.destino.codigo}, "
                    f"no para {destino.codigo}"
                )
            if any(detalle.pedido is pedido for detalle in detalles):
                raise ValueError(f"La línea de {pedido.producto.codigo} está repetida en el bulto")
            detalles.append(DetalleBulto(pedido, cantidad))
        return detalles

    def _comprometer_origen(self) -> None:
        """Descuenta el disponible del CD. Primero verifica todo para no dejar descuentos a medias."""
        origen = self._orden.origen
        for detalle in self._detalles:
            disponible = origen.disponible(detalle.producto.codigo)
            if disponible < detalle.cantidad:
                raise Conflicto(
                    f"Stock insuficiente en el CD de {detalle.producto.codigo}: "
                    f"disponible {disponible}, solicitado {detalle.cantidad}"
                )
        for detalle in self._detalles:
            origen.buscar_existencia(detalle.producto.codigo).retirar(detalle.cantidad)

    @classmethod
    def restaurar(cls, codigo, orden, destino, remito_numero, detalles: list[DetalleBulto],
                  estado: EstadoBulto, historial: list[CambioEstado],
                  precinto_numero=None, precinto_intacto=None) -> Bulto:
        """Reconstruye un bulto guardado, sin volver a descontar stock ni generar historial."""
        if not historial or historial[-1].nuevo != estado.nombre():
            raise ValueError(f"El historial del bulto {codigo} no coincide con su estado")
        bulto = cls.__new__(cls)
        bulto._codigo = codigo
        bulto._orden = orden
        bulto._destino = destino
        bulto._remito_numero = remito_numero
        bulto._detalles = list(detalles)
        bulto._estado = estado
        bulto._historial = list(historial)
        bulto._precinto_numero = precinto_numero
        bulto._precinto_intacto = precinto_intacto
        return bulto

    # --- Propiedades ---

    @property
    def codigo(self) -> str:
        return self._codigo

    @property
    def orden(self) -> OrdenReposicion:
        return self._orden

    @property
    def destino(self) -> Sucursal:
        return self._destino

    @property
    def remito_numero(self) -> str:
        return self._remito_numero

    @property
    def precinto_numero(self) -> str | None:
        return self._precinto_numero

    @property
    def precinto_intacto(self) -> bool | None:
        return self._precinto_intacto

    @property
    def detalles(self) -> list[DetalleBulto]:
        return list(self._detalles)

    @property
    def estado(self) -> EstadoBulto:
        return self._estado

    @property
    def historial(self) -> list[CambioEstado]:
        return list(self._historial)

    @property
    def fecha_preparacion(self) -> datetime:
        return self._historial[0].fecha

    def unidades(self) -> int:
        return sum(detalle.cantidad for detalle in self._detalles)

    def estado_remito(self) -> str:
        return self._estado.estado_remito()

    def acciones_permitidas(self) -> list[str]:
        return self._estado.acciones_permitidas()

    # --- Operaciones: se delegan en el estado actual ---

    def precintar(self, numero: str) -> None:
        self._estado.precintar(self, numero)

    def despachar(self) -> None:
        self._estado.despachar(self)

    def recibir(self, intacto: bool, motivo: str = "") -> None:
        self._estado.recibir(self, intacto, motivo)

    def verificar(self, conforme: bool, motivo: str = "") -> None:
        self._estado.verificar(self, conforme, motivo)

    # --- Operaciones de soporte que invocan los estados ---

    def cambiar_estado(self, nuevo: EstadoBulto, motivo: str = "") -> None:
        """Único punto donde cambia el estado: valida el sucesor y agrega un CambioEstado."""
        if not isinstance(nuevo, EstadoBulto):
            raise ValueError("nuevo: debe ser un EstadoBulto")
        if not self._estado.permite_sucesor(nuevo.nombre()):
            raise Conflicto(f"Transición no permitida: {self._estado.nombre()} -> {nuevo.nombre()}")
        cambio = CambioEstado(len(self._historial) + 1, ahora(), self._estado.nombre(), nuevo.nombre(), motivo)
        self._historial.append(cambio)
        self._estado = nuevo

    def registrar_precinto(self, numero: str) -> None:
        if not self._estado.permite_sucesor("PRECINTADO") or self._precinto_numero is not None:
            raise Conflicto("El precinto sólo se registra una vez, al precintar")
        self._precinto_numero = validar_texto(numero, "numero de precinto")

    def registrar_recepcion(self, intacto: bool) -> None:
        if not self._estado.permite_sucesor("RECIBIDO") or self._precinto_intacto is not None:
            raise Conflicto("La recepción sólo se registra una vez, al recibir")
        self._precinto_intacto = intacto

    def acreditar_destino(self) -> None:
        """Suma el contenido al disponible del local. Sólo es posible desde un estado que pueda pasar a VERIFICADO."""
        if not self._estado.permite_sucesor("VERIFICADO"):
            raise Conflicto(f"No se puede acreditar stock con el bulto en estado {self._estado.nombre()}")
        for detalle in self._detalles:
            self._destino.existencia_para(detalle.producto).ingresar(detalle.cantidad)

    def __repr__(self) -> str:
        return f"Bulto({self._codigo!r}, {self._estado.nombre()}, destino={self._destino.codigo!r})"


# ---------------------------------------------------------------------------
# Ventas y devoluciones
# ---------------------------------------------------------------------------


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
        """Reparte el total proporcionalmente al subtotal; la última línea absorbe los centavos."""
        subtotal = self.subtotal()
        acumulado = Decimal("0.00")
        for detalle in self._detalles[:-1]:
            importe = redondear(total * detalle.subtotal() / subtotal)
            detalle.asignar_importe(importe)
            acumulado += importe
        self._detalles[-1].asignar_importe(total - acumulado)

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
        """Importe proporcional al cobrado; la última devolución de la línea absorbe el residual."""
        importe_ya_devuelto = redondear(a_decimal(importe_ya_devuelto, "importe ya devuelto"))
        cobrado = self._detalle.importe_cobrado
        if cantidad_ya_devuelta + self._cantidad == self._detalle.cantidad:
            reintegro = cobrado - importe_ya_devuelto
        else:
            reintegro = redondear(cobrado * self._cantidad / self._detalle.cantidad)
        if reintegro < 0 or importe_ya_devuelto + reintegro > cobrado:
            raise Conflicto("El reintegro acumulado no puede superar lo cobrado en la línea")
        return reintegro

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
