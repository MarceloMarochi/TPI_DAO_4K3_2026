"""Fachada compatible: delega en cinco servicios con la misma conexión.

No incorpora el alcance ampliado TP3.1. Los ingresos siguen siendo simples y
cada devolución corresponde a una línea. Cada servicio conserva su transacción.
"""
from __future__ import annotations
from pathlib import Path
from app import config
from app.negocio.servicio_catalogo import ServicioCatalogo
from app.negocio.servicio_logistica import ServicioLogistica
from app.negocio.servicio_ventas import ServicioVentas
from app.negocio.servicio_reportes import ServicioReportes
from app.negocio.servicio_importacion import ServicioImportacion


class SistemaVentas:
    REPORTES = ServicioReportes.REPORTES

    def __init__(self, conexion, descuento_efectivo=config.TASA_DESCUENTO_EFECTIVO,
                 recargo_tarjeta=config.TASA_RECARGO_TARJETA):
        self._catalogo = ServicioCatalogo(conexion)
        self._logistica = ServicioLogistica(conexion)
        self._ventas = ServicioVentas(conexion, descuento_efectivo, recargo_tarjeta)
        self._reportes = ServicioReportes(conexion)
        self._importacion = ServicioImportacion(self._catalogo)

    def guardar_catalogo(self, tipo: str, datos: dict, alta: bool=True) -> dict:
        return self._catalogo.guardar_catalogo(tipo, datos, alta)

    def configurar_minimo(self, sucursal_codigo: str, producto_codigo: str, minimo) -> dict:
        return self._catalogo.configurar_minimo(sucursal_codigo, producto_codigo, minimo)

    def registrar_ingreso(self, datos: dict) -> dict:
        return self._catalogo.registrar_ingreso(datos)

    def consultar_catalogo(self, tipo: str | None=None) -> dict | list:
        return self._catalogo.consultar_catalogo(tipo)

    def consultar_existencias(self, sucursal_codigo: str | None=None, producto_codigo: str | None=None) -> list[dict]:
        return self._catalogo.consultar_existencias(sucursal_codigo, producto_codigo)

    def consultar_ingreso(self, numero: str) -> dict:
        return self._catalogo.consultar_ingreso(numero)

    def crear_orden(self, datos: dict) -> dict:
        return self._logistica.crear_orden(datos)

    def preparar_bulto(self, datos: dict) -> dict:
        return self._logistica.preparar_bulto(datos)

    def precintar(self, codigo: str, numero: str) -> dict:
        return self._logistica.precintar(codigo, numero)

    def despachar(self, codigo: str) -> dict:
        return self._logistica.despachar(codigo)

    def recibir(self, codigo: str, intacto: bool, motivo: str='') -> dict:
        return self._logistica.recibir(codigo, intacto, motivo)

    def verificar(self, codigo: str, conforme: bool, motivo: str='') -> dict:
        return self._logistica.verificar(codigo, conforme, motivo)

    def consultar_orden(self, numero: str) -> dict:
        return self._logistica.consultar_orden(numero)

    def listar_ordenes(self, solo_con_pendientes: bool=False) -> list[dict]:
        return self._logistica.listar_ordenes(solo_con_pendientes)

    def consultar_bulto(self, codigo: str) -> dict:
        return self._logistica.consultar_bulto(codigo)

    def listar_bultos(self, estado: str | None=None, destino_codigo: str | None=None) -> list[dict]:
        return self._logistica.listar_bultos(estado, destino_codigo)

    def cotizar_venta(self, datos: dict) -> dict:
        return self._ventas.cotizar_venta(datos)

    def confirmar_venta(self, datos: dict) -> dict:
        return self._ventas.confirmar_venta(datos)

    def devolver(self, datos: dict) -> dict:
        return self._ventas.devolver(datos)

    def consultar_venta(self, numero: str) -> dict:
        return self._ventas.consultar_venta(numero)

    def listar_ventas(self, local_codigo: str | None=None) -> list[dict]:
        return self._ventas.listar_ventas(local_codigo)

    def consultar_devolucion(self, numero: str) -> dict:
        return self._ventas.consultar_devolucion(numero)

    def consultar_medios_pago(self) -> list[dict]:
        return self._ventas.consultar_medios_pago()

    def consultar_reporte(self, nombre: str, filtros: dict) -> dict:
        return self._reportes.consultar_reporte(nombre, filtros)

    def importar_csv(self, tipo: str, ruta: str | Path) -> dict:
        return self._importacion.importar_csv(tipo, ruta)
