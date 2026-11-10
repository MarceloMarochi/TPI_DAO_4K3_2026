"""Casos de uso de logistica del alcance simplificado."""
from __future__ import annotations

from app.negocio.comunes import validar_texto
from app.negocio.errores import Conflicto, NoEncontrado
from app.negocio.conversiones import _a_entero
from app.negocio.servicio_base import ServicioBase
from app.datos.logistica_dao import LogisticaDAO
from app.negocio.bultos import Bulto
from app.negocio.reposicion import OrdenReposicion
from app.negocio.representaciones import _bulto_a_dict


class ServicioLogistica(ServicioBase):
    def __init__(self, conexion):
        super().__init__(conexion)
        self._logistica = LogisticaDAO(conexion)

    def _bulto(self, codigo) -> Bulto:
        bulto = self._logistica.buscar_bulto(codigo, self._productos, self._sucursales)
        if bulto is None:
            raise NoEncontrado(f"No existe el bulto {codigo}")
        return bulto

    def crear_orden(self, datos: dict) -> dict:
        """datos: {numero, necesidades: [{destino_codigo, producto_codigo, cantidad}]}"""
        with self._escritura():
            numero = validar_texto(datos.get("numero"), "numero")
            if self._logistica.buscar_orden(numero, self._productos, self._sucursales) is not None:
                raise Conflicto(f"Ya existe la orden {numero}")
            orden = OrdenReposicion(numero, self._cd())
            for necesidad in datos.get("necesidades") or []:
                orden.agregar_necesidad(
                    self._sucursal(necesidad.get("destino_codigo")),
                    self._producto(necesidad.get("producto_codigo")),
                    _a_entero(necesidad.get("cantidad"), "cantidad"),
                )
            orden.validar()
            self._logistica.guardar_orden(orden)
            return self._orden_a_dict(orden)

    def preparar_bulto(self, datos: dict) -> dict:
        """datos: {codigo, orden_numero, destino_codigo, remito_numero, lineas: [{detalle_id, cantidad}]}

        Descuenta el disponible del CD una única vez y cierra la orden.
        """
        with self._escritura():
            codigo = validar_texto(datos.get("codigo"), "codigo")
            remito = validar_texto(datos.get("remito_numero"), "remito_numero")
            if self._logistica.buscar_bulto(codigo, self._productos, self._sucursales) is not None:
                raise Conflicto(f"Ya existe el bulto {codigo}")
            if self._logistica.remito_en_uso(remito):
                raise Conflicto(f"El remito {remito} ya está asignado a otro bulto")
            orden = self._logistica.buscar_orden(datos.get("orden_numero"), self._productos, self._sucursales)
            if orden is None:
                raise NoEncontrado(f"No existe la orden {datos.get('orden_numero')}")
            destino = self._sucursal(datos.get("destino_codigo"))

            contenido = []
            for linea in datos.get("lineas") or []:
                pedido = orden.buscar_detalle(linea.get("detalle_id"))
                if pedido is None:
                    raise ValueError(f"detalle_id: la línea {linea.get('detalle_id')} no pertenece a la orden")
                cantidad = _a_entero(linea.get("cantidad"), "cantidad")
                pendiente = pedido.pendiente(self._logistica.asignado_a_detalle(pedido.id))
                if cantidad > pendiente:
                    raise Conflicto(
                        f"De {pedido.producto.codigo} para {pedido.destino.codigo} quedan {pendiente} "
                        f"unidades pendientes de preparar; se pidieron {cantidad}"
                    )
                contenido.append((pedido, cantidad))

            bulto = Bulto(codigo, orden, destino, remito, contenido)
            self._logistica.guardar_orden(orden)  # queda cerrada
            self._logistica.guardar_bulto(bulto)
            self._catalogo.guardar_existencias(orden.origen)
            return _bulto_a_dict(bulto)

    def precintar(self, codigo: str, numero: str) -> dict:
        with self._escritura():
            numero = validar_texto(numero, "numero de precinto")
            if self._logistica.precinto_en_uso(numero):
                raise Conflicto(f"El precinto {numero} ya está asignado a otro bulto")
            return self._operar_bulto(codigo, lambda bulto: bulto.precintar(numero))

    def despachar(self, codigo: str) -> dict:
        with self._escritura():
            return self._operar_bulto(codigo, lambda bulto: bulto.despachar())

    def recibir(self, codigo: str, intacto: bool, motivo: str = "") -> dict:
        with self._escritura():
            return self._operar_bulto(codigo, lambda bulto: bulto.recibir(intacto, motivo or ""))

    def verificar(self, codigo: str, conforme: bool, motivo: str = "") -> dict:
        with self._escritura():
            return self._operar_bulto(codigo, lambda bulto: bulto.verificar(conforme, motivo or ""))

    def _operar_bulto(self, codigo, operacion) -> dict:
        """El bulto decide (State); acá sólo se guarda el resultado y el stock del destino."""
        bulto = self._bulto(codigo)
        operacion(bulto)
        self._logistica.guardar_bulto(bulto)
        self._catalogo.guardar_existencias(bulto.destino)
        return _bulto_a_dict(bulto)

    def consultar_orden(self, numero: str) -> dict:
        self._cargar()
        orden = self._logistica.buscar_orden(numero, self._productos, self._sucursales)
        if orden is None:
            raise NoEncontrado(f"No existe la orden {numero}")
        return self._orden_a_dict(orden)

    def listar_ordenes(self, solo_con_pendientes: bool = False) -> list[dict]:
        return self._logistica.listar_ordenes(solo_con_pendientes)

    def consultar_bulto(self, codigo: str) -> dict:
        self._cargar()
        return _bulto_a_dict(self._bulto(codigo))

    def listar_bultos(self, estado: str | None = None, destino_codigo: str | None = None) -> list[dict]:
        return self._logistica.listar_bultos(estado, destino_codigo)

    def _orden_a_dict(self, orden: OrdenReposicion) -> dict:
        return {
            "numero": orden.numero, "fecha": orden.fecha, "origen_codigo": orden.origen.codigo,
            "cerrada": orden.cerrada, "detalles": self._logistica.pendientes_de_orden(orden.numero),
        }
