"""Bultos, contenido e historial inmutable del circuito logístico."""
from __future__ import annotations

from datetime import datetime

from app.negocio.comunes import ahora, validar_fecha, validar_positivo, validar_texto
from app.negocio.errores import Conflicto
from app.negocio.catalogo_stock import Producto, Sucursal, _validar_sucursal
from app.negocio.reposicion import OrdenReposicion, DetalleReposicion
from app.negocio.estados import EstadoBulto, Preparado


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
        self._ejecutar("precintar", numero)

    def despachar(self) -> None:
        self._ejecutar("despachar")

    def recibir(self, intacto: bool, motivo: str = "") -> None:
        self._ejecutar("recibir", intacto, motivo)

    def verificar(self, conforme: bool, motivo: str = "") -> None:
        self._ejecutar("verificar", conforme, motivo)

    def _ejecutar(self, operacion: str, *argumentos) -> None:
        """State valida sin mutar; luego se aplican juntos estado, evidencia y stock.

        No hay operaciones públicas para acreditar o cambiar el estado de forma
        aislada. El servicio persiste el resultado en una única transacción.
        """
        transicion = getattr(self._estado, operacion)(self, *argumentos)
        nuevo = transicion.nuevo
        if not self._estado.permite_sucesor(nuevo.nombre()):
            raise Conflicto(f"Transición no permitida: {self._estado.nombre()} -> {nuevo.nombre()}")
        if transicion.precinto is not None and self._precinto_numero is not None:
            raise Conflicto("El precinto sólo se registra una vez")
        if transicion.intacto is not None and self._precinto_intacto is not None:
            raise Conflicto("La recepción sólo se registra una vez")
        cambio = CambioEstado(len(self._historial) + 1, ahora(), self._estado.nombre(),
                              nuevo.nombre(), transicion.motivo)
        # Construir y validar la evidencia antes de modificar existencias.
        ingresos = [(self._destino.existencia_para(d.producto), d.cantidad)
                    for d in self._detalles] if transicion.acreditar else []
        for existencia, cantidad in ingresos:
            existencia.ingresar(cantidad)
        if transicion.precinto is not None:
            self._precinto_numero = transicion.precinto
        if transicion.intacto is not None:
            self._precinto_intacto = transicion.intacto
        self._historial.append(cambio)
        self._estado = nuevo

    def __repr__(self) -> str:
        return f"Bulto({self._codigo!r}, {self._estado.nombre()}, destino={self._destino.codigo!r})"
