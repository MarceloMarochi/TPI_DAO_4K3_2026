"""Importaciones compatibles. Las clases viven en módulos por responsabilidad."""
from app.negocio.catalogo_stock import Producto, Existencia, Sucursal, IngresoStock
from app.negocio.reposicion import OrdenReposicion, DetalleReposicion
from app.negocio.bultos import Bulto, DetalleBulto, CambioEstado
from app.negocio.ventas import Venta, DetalleVenta
from app.negocio.devoluciones import Devolucion

__all__ = [
    "Producto", "Existencia", "Sucursal", "IngresoStock", "OrdenReposicion",
    "DetalleReposicion", "Bulto", "DetalleBulto", "CambioEstado", "Venta",
    "DetalleVenta", "Devolucion",
]
