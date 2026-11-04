"""LogisticaDAO y VentaDAO: guardar, reconstruir y respetar la inmutabilidad."""

import sqlite3
from decimal import Decimal

import pytest

from app.negocio.estados import EnTransito, Verificado
from app.negocio.modelos import Bulto, Devolucion, OrdenReposicion, Venta
from app.negocio.pagos import Efectivo, Tarjeta

from .conftest import recargar


def crear_orden_y_bulto(conexion, catalogo_dao, logistica_dao, cantidad=10):
    """Orden con una línea para L01 y un bulto preparado, todo guardado en una transacción."""
    productos, sucursales = recargar(conexion)
    with conexion.transaccion():
        orden = OrdenReposicion("O-1", sucursales["CD"])
        linea = orden.agregar_necesidad(sucursales["L01"], productos["P001"], cantidad)
        logistica_dao.guardar_orden(orden)
        bulto = Bulto("B-1", orden, sucursales["L01"], "R-1", [(linea, cantidad)])
        logistica_dao.guardar_orden(orden)
        logistica_dao.guardar_bulto(bulto)
        catalogo_dao.guardar_existencias(sucursales["CD"])
    return bulto


class TestOrdenes:
    def test_orden_ida_y_vuelta(self, conexion, logistica_dao, con_catalogo):
        productos, sucursales = recargar(conexion)
        orden = OrdenReposicion("O-1", sucursales["CD"])
        orden.agregar_necesidad(sucursales["L01"], productos["P001"], 5)
        orden.agregar_necesidad(sucursales["L01"], productos["P001"], 3)
        orden.agregar_necesidad(sucursales["L02"], productos["P002"], 4)
        logistica_dao.guardar_orden(orden)

        leida = logistica_dao.buscar_orden("O-1", productos, sucursales)
        assert [(d.destino.codigo, d.producto.codigo, d.cantidad) for d in leida.detalles] == [
            ("L01", "P001", 8), ("L02", "P002", 4)
        ]
        assert all(d.id is not None for d in leida.detalles)
        assert not leida.cerrada

    def test_orden_inexistente(self, conexion, logistica_dao, con_catalogo):
        productos, sucursales = recargar(conexion)
        assert logistica_dao.buscar_orden("NO", productos, sucursales) is None

    def test_pendientes_y_cierre(self, conexion, catalogo_dao, logistica_dao, con_catalogo):
        crear_orden_y_bulto(conexion, catalogo_dao, logistica_dao, cantidad=10)
        ordenes = logistica_dao.listar_ordenes()
        assert ordenes[0] | {"fecha": None} == {
            "numero": "O-1", "fecha": None, "origen_codigo": "CD", "cerrada": True,
            "solicitado": 10, "asignado": 10, "pendiente": 0,
        }
        assert logistica_dao.listar_ordenes(solo_con_pendientes=True) == []


class TestBultos:
    def test_bulto_preparado_ida_y_vuelta(self, conexion, catalogo_dao, logistica_dao, con_catalogo):
        crear_orden_y_bulto(conexion, catalogo_dao, logistica_dao)
        productos, sucursales = recargar(conexion)

        bulto = logistica_dao.buscar_bulto("B-1", productos, sucursales)
        assert bulto.estado.nombre() == "PREPARADO"
        assert [(d.producto.codigo, d.cantidad) for d in bulto.detalles] == [("P001", 10)]
        assert bulto.orden.cerrada
        assert sucursales["CD"].disponible("P001") == 90  # el descuento se persistió
        assert logistica_dao.asignado_a_detalle(bulto.detalles[0].pedido.id) == 10

    def test_recorrido_completo_persistido(self, conexion, catalogo_dao, logistica_dao, con_catalogo):
        crear_orden_y_bulto(conexion, catalogo_dao, logistica_dao)

        # Cada operación es una solicitud distinta: se recarga todo desde la base.
        operaciones = [
            lambda b: b.precintar("PR-1"),
            lambda b: b.despachar(),
            lambda b: b.recibir(True),
            lambda b: b.verificar(True),
        ]
        for operar in operaciones:
            productos, sucursales = recargar(conexion)
            with conexion.transaccion():
                bulto = logistica_dao.buscar_bulto("B-1", productos, sucursales)
                operar(bulto)
                logistica_dao.guardar_bulto(bulto)
                catalogo_dao.guardar_existencias(bulto.destino)

        productos, sucursales = recargar(conexion)
        bulto = logistica_dao.buscar_bulto("B-1", productos, sucursales)
        assert isinstance(bulto.estado, Verificado)
        assert [c.secuencia for c in bulto.historial] == [1, 2, 3, 4, 5]
        assert bulto.precinto_numero == "PR-1" and bulto.precinto_intacto is True
        assert sucursales["L01"].disponible("P001") == 10
        assert sucursales["CD"].disponible("P001") == 90

    def test_falla_dentro_de_la_transaccion_no_deja_rastros(self, conexion, catalogo_dao, logistica_dao,
                                                            con_catalogo):
        crear_orden_y_bulto(conexion, catalogo_dao, logistica_dao)
        productos, sucursales = recargar(conexion)
        with pytest.raises(RuntimeError):
            with conexion.transaccion():
                bulto = logistica_dao.buscar_bulto("B-1", productos, sucursales)
                bulto.precintar("PR-1")
                logistica_dao.guardar_bulto(bulto)
                raise RuntimeError("se corta la luz")
        productos, sucursales = recargar(conexion)
        bulto = logistica_dao.buscar_bulto("B-1", productos, sucursales)
        assert bulto.estado.nombre() == "PREPARADO"
        assert len(bulto.historial) == 1

    def test_historial_inmutable_en_la_base(self, conexion, catalogo_dao, logistica_dao, con_catalogo):  # RN-18
        crear_orden_y_bulto(conexion, catalogo_dao, logistica_dao)
        with pytest.raises(sqlite3.IntegrityError, match="inmutable"):
            conexion.ejecutar("UPDATE historial_estados SET nuevo = 'VERIFICADO'")
        with pytest.raises(sqlite3.IntegrityError, match="inmutable"):
            conexion.ejecutar("DELETE FROM historial_estados")

    def test_remito_unico(self, conexion, catalogo_dao, logistica_dao, con_catalogo):  # RN-14
        crear_orden_y_bulto(conexion, catalogo_dao, logistica_dao, cantidad=5)
        productos, sucursales = recargar(conexion)
        orden = OrdenReposicion("O-2", sucursales["CD"])
        linea = orden.agregar_necesidad(sucursales["L01"], productos["P001"], 5)
        logistica_dao.guardar_orden(orden)
        otro = Bulto("B-2", orden, sucursales["L01"], "R-1", [(linea, 5)])
        with pytest.raises(sqlite3.IntegrityError):
            logistica_dao.guardar_bulto(otro)

    def test_listar_bultos_por_estado(self, conexion, catalogo_dao, logistica_dao, con_catalogo):
        crear_orden_y_bulto(conexion, catalogo_dao, logistica_dao)
        assert [b["codigo"] for b in logistica_dao.listar_bultos(estado="PREPARADO")] == ["B-1"]
        assert logistica_dao.listar_bultos(estado=EnTransito().nombre()) == []
        assert logistica_dao.listar_bultos(destino_codigo="L01")[0]["unidades"] == 10


def abastecer_l01(conexion, catalogo_dao, logistica_dao):
    """Deja 10 unidades de P001 verificadas y disponibles en L01."""
    crear_orden_y_bulto(conexion, catalogo_dao, logistica_dao)
    productos, sucursales = recargar(conexion)
    with conexion.transaccion():
        bulto = logistica_dao.buscar_bulto("B-1", productos, sucursales)
        bulto.precintar("PR-1")
        bulto.despachar()
        bulto.recibir(True)
        bulto.verificar(True)
        logistica_dao.guardar_bulto(bulto)
        catalogo_dao.guardar_existencias(bulto.destino)


@pytest.fixture
def con_stock_en_local(conexion, catalogo_dao, logistica_dao, con_catalogo):
    abastecer_l01(conexion, catalogo_dao, logistica_dao)


def vender(conexion, catalogo_dao, venta_dao, numero, medio, cantidad):
    productos, sucursales = recargar(conexion)
    with conexion.transaccion():
        venta = Venta(numero, sucursales["L01"], medio)
        venta.agregar_detalle(productos["P001"], cantidad)
        venta.confirmar()
        venta_dao.insertar_venta(venta)
        catalogo_dao.guardar_existencias(venta.local)
    return venta


class TestVentas:
    def test_venta_ida_y_vuelta(self, conexion, catalogo_dao, venta_dao, con_stock_en_local):
        vender(conexion, catalogo_dao, venta_dao, "V-1", Tarjeta("0.10"), 3)
        productos, sucursales = recargar(conexion)

        venta = venta_dao.buscar_venta("V-1", productos, sucursales)
        assert venta.confirmada
        assert isinstance(venta.medio, Tarjeta) and venta.tasa_aplicada == Decimal("0.10")
        assert venta.total_cobrado == Decimal("3300.00")
        assert venta.detalles[0].importe_cobrado == Decimal("3300.00")
        assert venta.comprobante_numero == "CI-V-1"
        assert sucursales["L01"].disponible("P001") == 7

    def test_venta_inmutable_en_la_base(self, conexion, catalogo_dao, venta_dao, con_stock_en_local):  # RN-21
        vender(conexion, catalogo_dao, venta_dao, "V-1", Efectivo("0"), 1)
        with pytest.raises(sqlite3.IntegrityError, match="no se modifica"):
            conexion.ejecutar("UPDATE ventas SET total_cobrado_centavos = 0")
        with pytest.raises(sqlite3.IntegrityError, match="no se modifica"):
            conexion.ejecutar("DELETE FROM detalles_venta")

    def test_numero_de_venta_unico(self, conexion, catalogo_dao, venta_dao, con_stock_en_local):
        vender(conexion, catalogo_dao, venta_dao, "V-1", Efectivo("0"), 1)
        with pytest.raises(sqlite3.IntegrityError):
            vender(conexion, catalogo_dao, venta_dao, "V-1", Efectivo("0"), 1)
        _, sucursales = recargar(conexion)
        assert sucursales["L01"].disponible("P001") == 9  # el segundo intento se revirtió

    def test_no_guarda_borradores(self, conexion, venta_dao, con_stock_en_local):
        _, sucursales = recargar(conexion)
        with pytest.raises(ValueError, match="confirmadas"):
            venta_dao.insertar_venta(Venta("V-9", sucursales["L01"], Efectivo("0")))

    def test_devoluciones_acumuladas(self, conexion, catalogo_dao, venta_dao, con_stock_en_local):
        vender(conexion, catalogo_dao, venta_dao, "V-1", Efectivo("0"), 5)

        for numero, cantidad, apta in [("D-1", 2, True), ("D-2", 3, False)]:
            productos, sucursales = recargar(conexion)
            with conexion.transaccion():
                venta = venta_dao.buscar_venta("V-1", productos, sucursales)
                detalle = venta.detalles[0]
                ya_cantidad, ya_importe = venta_dao.acumulado_devuelto(detalle.id)
                devolucion = Devolucion(numero, venta, detalle, cantidad, apta, "Prueba")
                devolucion.confirmar(ya_cantidad, ya_importe)
                venta_dao.insertar_devolucion(devolucion)
                catalogo_dao.guardar_existencias(venta.local)

        productos, sucursales = recargar(conexion)
        venta = venta_dao.buscar_venta("V-1", productos, sucursales)
        assert venta_dao.acumulado_devuelto(venta.detalles[0].id) == (5, Decimal("5000.00"))
        assert sucursales["L01"].disponible("P001") == 5 + 2  # sólo vuelve lo apto

        devolucion = venta_dao.buscar_devolucion("D-2", productos, sucursales)
        assert (devolucion.cantidad, devolucion.apta_reventa) == (3, False)
        assert devolucion.importe_reintegrado == Decimal("3000.00")

    def test_listar_ventas(self, conexion, catalogo_dao, venta_dao, con_stock_en_local):
        vender(conexion, catalogo_dao, venta_dao, "V-1", Efectivo("0.10"), 1)
        filas = venta_dao.listar_ventas("L01")
        assert [(f["numero"], f["total_cobrado"]) for f in filas] == [("V-1", Decimal("900.00"))]
