"""Casos de uso de ventas del alcance simplificado."""
from __future__ import annotations

from decimal import Decimal
from app import config
from app.negocio.comunes import validar_texto
from app.negocio.comunes import validar_total_esperado
from app.negocio.errores import Conflicto, NoEncontrado
from app.negocio.conversiones import _a_entero, _a_bool
from app.negocio.servicio_base import ServicioBase
from app.datos.venta_dao import VentaDAO
from app.negocio.ventas import Venta
from app.negocio.devoluciones import Devolucion
from app.negocio.pagos import MedioPago, Efectivo, Tarjeta
from app.negocio.representaciones import _devolucion_a_dict


class ServicioVentas(ServicioBase):
    def __init__(self, conexion, descuento_efectivo=config.TASA_DESCUENTO_EFECTIVO, recargo_tarjeta=config.TASA_RECARGO_TARJETA):
        super().__init__(conexion)
        self._ventas = VentaDAO(conexion)
        self._medios = {Efectivo.CODIGO: Efectivo(descuento_efectivo), Tarjeta.CODIGO: Tarjeta(recargo_tarjeta)}

    def _medio(self, codigo) -> MedioPago:
        medio = self._medios.get(codigo)
        if medio is None:
            raise ValueError(f"medio_codigo: medio de pago desconocido ({codigo})")
        return medio

    def _venta(self, numero) -> Venta:
        venta = self._ventas.buscar_venta(numero, self._productos, self._sucursales)
        if venta is None:
            raise NoEncontrado(f"No existe la venta {numero}")
        return venta

    def _armar_venta(self, numero, datos) -> Venta:
        venta = Venta(numero, self._sucursal(datos.get("local_codigo")), self._medio(datos.get("medio_codigo")))
        items = datos.get("items") or []
        if not items:
            raise ValueError("items: la venta debe tener al menos un producto")
        for item in items:
            venta.agregar_detalle(self._producto(item.get("producto_codigo")),
                                  _a_entero(item.get("cantidad"), "cantidad"))
        return venta

    def cotizar_venta(self, datos: dict) -> dict:
        """Calcula subtotal, ajuste y total. No guarda ni reserva stock.

        datos: {local_codigo, medio_codigo, items: [{producto_codigo, cantidad}]}
        """
        self._cargar()
        venta = self._armar_venta("COTIZACION", datos)
        return {
            "local_codigo": venta.local.codigo,
            "medio_codigo": venta.medio_codigo,
            "tasa": venta.tasa_aplicada,
            "lineas": [
                {"producto_codigo": d.producto.codigo, "producto_nombre": d.producto.nombre,
                 "cantidad": d.cantidad, "precio_unitario": d.precio_unitario, "subtotal": d.subtotal()}
                for d in venta.detalles
            ],
            "subtotal": venta.subtotal(),
            "ajuste": venta.ajuste(),
            "total": venta.calcular_total(),
        }

    def confirmar_venta(self, datos: dict) -> dict:
        """Igual que cotizar más {numero, total_esperado}. Recalcula todo en el servidor.

        Si el total difiere del que vio el usuario (cambió un precio), no guarda y pide cotizar de nuevo.
        """
        with self._escritura():
            numero = validar_texto(datos.get("numero"), "numero")
            if self._ventas.buscar_venta(numero, self._productos, self._sucursales) is not None:
                raise Conflicto(f"Ya existe la venta {numero}")
            venta = self._armar_venta(numero, datos)
            esperado = validar_total_esperado(datos.get("total_esperado"))
            if esperado != venta.calcular_total():
                raise Conflicto(
                    f"El total cambió: se esperaba {esperado} y ahora es {venta.calcular_total()}. "
                    "Vuelva a cotizar."
                )
            venta.confirmar()
            self._ventas.insertar_venta(venta)
            self._catalogo.guardar_existencias(venta.local)
            return self._venta_a_dict(venta)

    def devolver(self, datos: dict) -> dict:
        """datos: {numero, venta_numero, detalle_id, cantidad, apta_reventa, motivo}"""
        with self._escritura():
            numero = validar_texto(datos.get("numero"), "numero")
            if self._ventas.buscar_devolucion(numero, self._productos, self._sucursales) is not None:
                raise Conflicto(f"Ya existe la devolución {numero}")
            venta = self._venta(datos.get("venta_numero"))
            detalle = venta.buscar_detalle(datos.get("detalle_id"))
            if detalle is None:
                raise ValueError(f"detalle_id: la línea {datos.get('detalle_id')} no pertenece a la venta")
            ya_devuelto, importe_ya_devuelto = self._ventas.acumulado_devuelto(detalle.id)
            devolucion = Devolucion(numero, venta, detalle, _a_entero(datos.get("cantidad"), "cantidad"),
                                    _a_bool(datos.get("apta_reventa"), "apta_reventa"), datos.get("motivo"))
            devolucion.confirmar(ya_devuelto, importe_ya_devuelto)
            self._ventas.insertar_devolucion(devolucion)
            self._catalogo.guardar_existencias(venta.local)
            return _devolucion_a_dict(devolucion)

    def consultar_venta(self, numero: str) -> dict:
        self._cargar()
        return self._venta_a_dict(self._venta(numero))

    def listar_ventas(self, local_codigo: str | None = None) -> list[dict]:
        return self._ventas.listar_ventas(local_codigo)

    def consultar_devolucion(self, numero: str) -> dict:
        self._cargar()
        devolucion = self._ventas.buscar_devolucion(numero, self._productos, self._sucursales)
        if devolucion is None:
            raise NoEncontrado(f"No existe la devolución {numero}")
        return _devolucion_a_dict(devolucion)

    def consultar_medios_pago(self) -> list[dict]:
        return [
            {"codigo": Efectivo.CODIGO, "tipo": "descuento", "tasa": self._medios[Efectivo.CODIGO].tasa},
            {"codigo": Tarjeta.CODIGO, "tipo": "recargo", "tasa": self._medios[Tarjeta.CODIGO].tasa},
        ]

    def _venta_a_dict(self, venta: Venta) -> dict:
        devuelto = self._ventas.devuelto_por_detalle(venta.numero)
        subtotal = venta.subtotal()
        lineas = []
        for d in venta.detalles:
            cantidad_devuelta, importe_devuelto = devuelto.get(d.id, (0, Decimal("0.00")))
            lineas.append({
                "id": d.id, "producto_codigo": d.producto.codigo, "producto_nombre": d.producto.nombre,
                "cantidad": d.cantidad, "precio_unitario": d.precio_unitario, "subtotal": d.subtotal(),
                "importe_cobrado": d.importe_cobrado, "cantidad_devuelta": cantidad_devuelta,
                "importe_devuelto": importe_devuelto, "cantidad_restante": d.cantidad - cantidad_devuelta,
            })
        return {
            "numero": venta.numero, "fecha": venta.fecha, "local_codigo": venta.local.codigo,
            "local_nombre": venta.local.nombre, "medio_codigo": venta.medio_codigo, "tasa_aplicada": venta.tasa_aplicada,
            "subtotal": subtotal, "ajuste": venta.total_cobrado - subtotal,
            "total_cobrado": venta.total_cobrado, "comprobante_numero": venta.comprobante_numero,
            "lineas": lineas,
        }
