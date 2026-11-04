"""ConexionSQLite y CatalogoDAO."""

import sqlite3
from decimal import Decimal

import pytest

from app.datos.formatos import a_centavos, desde_centavos, fecha_a_texto, texto_a_fecha
from app.negocio.comunes import ahora
from app.negocio.modelos import IngresoStock, Producto, Sucursal

from .conftest import recargar

TABLAS = {
    "proveedores", "productos", "sucursales", "existencias", "ingresos_stock", "ordenes",
    "detalles_reposicion", "bultos", "detalles_bulto", "historial_estados", "ventas",
    "detalles_venta", "devoluciones",
}


class TestConexion:
    def test_crea_las_13_tablas(self, conexion):
        filas = conexion.consultar("SELECT name FROM sqlite_master WHERE type = 'table'")
        assert TABLAS <= {fila["name"] for fila in filas}

    def test_esquema_idempotente(self, conexion):
        conexion.crear_esquema()

    def test_commit(self, conexion, catalogo_dao):
        with conexion.transaccion():
            catalogo_dao.guardar_proveedor({"codigo": "PRV01", "nombre": "Uno"})
        assert len(catalogo_dao.listar_proveedores()) == 1

    def test_rollback_ante_error(self, conexion, catalogo_dao):
        with pytest.raises(ValueError):
            with conexion.transaccion():
                catalogo_dao.guardar_proveedor({"codigo": "PRV01", "nombre": "Uno"})
                raise ValueError("falla de negocio")
        assert catalogo_dao.listar_proveedores() == []
        assert not conexion.en_transaccion

    def test_no_admite_transacciones_anidadas(self, conexion):
        with conexion.transaccion():
            with pytest.raises(RuntimeError):
                with conexion.transaccion():
                    pass

    def test_claves_foraneas_activas(self, conexion, catalogo_dao):
        with pytest.raises(sqlite3.IntegrityError):
            catalogo_dao.guardar_producto(Producto("P1", "X", "C", "NO_EXISTE", "1", "1"))


class TestFormatos:
    def test_centavos_ida_y_vuelta(self):
        assert a_centavos(Decimal("1234.56")) == 123456
        assert desde_centavos(123456) == Decimal("1234.56")

    def test_fechas_de_ancho_fijo(self):
        fecha = ahora().replace(microsecond=0)
        texto = fecha_a_texto(fecha)
        assert texto.endswith("-03:00") and ".000000" in texto
        assert texto_a_fecha(texto) == fecha


class TestCatalogoDAO:
    def test_un_solo_cd(self, catalogo_dao):  # RN-03
        catalogo_dao.guardar_sucursal(Sucursal("CD", "CD", es_cd=True))
        with pytest.raises(sqlite3.IntegrityError):
            catalogo_dao.guardar_sucursal(Sucursal("CD2", "Otro CD", es_cd=True))

    def test_proveedor_actualiza_nombre_sin_duplicar(self, catalogo_dao):  # RN-01
        catalogo_dao.guardar_proveedor({"codigo": "PRV01", "nombre": "Viejo"})
        catalogo_dao.guardar_proveedor({"codigo": "PRV01", "nombre": "Nuevo"})
        assert catalogo_dao.listar_proveedores() == [{"codigo": "PRV01", "nombre": "Nuevo"}]

    def test_carga_catalogo_con_existencias(self, conexion, con_catalogo):
        productos, sucursales = recargar(conexion)
        assert set(productos) == {"P001", "P002"}
        assert productos["P001"].precio == Decimal("1000.00")
        assert sucursales["CD"].es_cd
        assert sucursales["CD"].disponible("P001") == 100
        assert sucursales["L01"].existencias == []

    def test_existencia_negativa_rechazada_por_la_base(self, conexion, con_catalogo):
        with pytest.raises(sqlite3.IntegrityError):
            conexion.ejecutar("UPDATE existencias SET cantidad = -1 WHERE producto_codigo = 'P001'")

    def test_guarda_minimo(self, conexion, catalogo_dao, con_catalogo):
        productos, sucursales = recargar(conexion)
        sucursales["L01"].existencia_para(productos["P001"]).minimo = 10
        catalogo_dao.guardar_existencias(sucursales["L01"])
        fila = catalogo_dao.consultar_existencias("L01", "P001")[0]
        assert (fila["disponible"], fila["minimo"], fila["faltante"]) == (0, 10, 10)

    def test_ingreso_ida_y_vuelta(self, conexion, catalogo_dao, con_catalogo):
        productos, _ = recargar(conexion)
        ingreso = catalogo_dao.buscar_ingreso("I-1", productos)
        assert (ingreso.producto.codigo, ingreso.cantidad, ingreso.costo_unitario) == ("P001", 100, Decimal("600.00"))
        assert catalogo_dao.buscar_ingreso("NO", productos) is None

    def test_ingreso_duplicado(self, conexion, catalogo_dao, con_catalogo):  # RN-06
        productos, _ = recargar(conexion)
        with pytest.raises(sqlite3.IntegrityError):
            catalogo_dao.insertar_ingreso(IngresoStock("I-1", productos["P001"], "PRV01", 1, "1"))

    def test_ingreso_inmutable(self, conexion, con_catalogo):
        with pytest.raises(sqlite3.IntegrityError, match="no se modifica"):
            conexion.ejecutar("UPDATE ingresos_stock SET cantidad = 1")
        with pytest.raises(sqlite3.IntegrityError, match="no se modifica"):
            conexion.ejecutar("DELETE FROM ingresos_stock")

    def test_listar_catalogos(self, catalogo_dao, con_catalogo):
        catalogos = catalogo_dao.listar_catalogos()
        assert [s["codigo"] for s in catalogos["sucursales"]] == ["CD", "L01", "L02"]
        assert catalogos["productos"][0]["precio"] == Decimal("1000.00")
