"""Base SQLite en memoria con un catálogo mínimo para probar los DAOs."""

import pytest

from app.datos.catalogo_dao import CatalogoDAO
from app.datos.conexion import ConexionSQLite
from app.datos.logistica_dao import LogisticaDAO
from app.datos.venta_dao import VentaDAO
from app.negocio.modelos import IngresoStock, Producto, Sucursal


@pytest.fixture
def conexion():
    conexion = ConexionSQLite(":memory:")
    conexion.crear_esquema()
    yield conexion
    conexion.cerrar()


@pytest.fixture
def catalogo_dao(conexion):
    return CatalogoDAO(conexion)


@pytest.fixture
def logistica_dao(conexion):
    return LogisticaDAO(conexion)


@pytest.fixture
def venta_dao(conexion):
    return VentaDAO(conexion)


@pytest.fixture
def con_catalogo(conexion, catalogo_dao):
    """Guarda proveedor, CD, dos locales, dos productos y 100 unidades de cada uno en el CD."""
    with conexion.transaccion():
        catalogo_dao.guardar_proveedor({"codigo": "PRV01", "nombre": "Distribuidora Sur"})
        cd = Sucursal("CD", "Centro de Distribución", es_cd=True)
        locales = [Sucursal("L01", "Local Centro"), Sucursal("L02", "Local Norte")]
        for sucursal in [cd, *locales]:
            catalogo_dao.guardar_sucursal(sucursal)
        productos = [
            Producto("P001", "Yerba 1 kg", "Almacén", "PRV01", "1000", "600"),
            Producto("P002", "Azúcar 1 kg", "Almacén", "PRV01", "500", "300"),
        ]
        for producto in productos:
            catalogo_dao.guardar_producto(producto)
        for i, producto in enumerate(productos, start=1):
            ingreso = IngresoStock(f"I-{i}", producto, "PRV01", 100, producto.costo_referencia)
            ingreso.aplicar(cd)
            catalogo_dao.insertar_ingreso(ingreso)
            catalogo_dao.guardar_producto(producto)
        catalogo_dao.guardar_existencias(cd)


def recargar(conexion):
    """Vuelve a leer productos y sucursales, como haría una solicitud nueva."""
    return CatalogoDAO(conexion).cargar_catalogo()
