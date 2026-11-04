"""Ventas (contexto Strategy) y devoluciones."""

from decimal import Decimal

import pytest

from app.negocio.modelos import Devolucion, Producto, Venta
from app.negocio.pagos import Efectivo, Tarjeta

from .conftest import abastecer_local, preparar_bulto


@pytest.fixture
def local_abastecido(cd_abastecido, local, yerba, azucar):
    abastecer_local(cd_abastecido, local, {yerba: 20, azucar: 20})
    return local


def venta_confirmada(local, medio, items: dict, numero="V-1") -> Venta:
    venta = Venta(numero, local, medio)
    for producto, cantidad in items.items():
        venta.agregar_detalle(producto, cantidad)
    venta.confirmar()
    return venta


class TestVenta:
    def test_no_se_vende_en_el_cd(self, cd):
        with pytest.raises(ValueError, match="CD"):
            Venta("V-1", cd, Efectivo("0"))

    def test_no_se_vende_mercaderia_sin_verificar(self, cd_abastecido, local, yerba):  # RN-17, RN-20
        bulto = preparar_bulto(cd_abastecido, local, {yerba: 10})
        bulto.precintar("PR-1")
        bulto.despachar()
        bulto.recibir(intacto=True)
        with pytest.raises(ValueError, match="Stock insuficiente"):
            Venta("V-1", local, Efectivo("0")).agregar_detalle(yerba, 1)

    def test_no_supera_el_disponible(self, local_abastecido, yerba):  # RN-20
        venta = Venta("V-1", local_abastecido, Efectivo("0"))
        venta.agregar_detalle(yerba, 15)
        with pytest.raises(ValueError, match="solicitado 21"):
            venta.agregar_detalle(yerba, 6)

    def test_mismo_producto_suma_en_una_linea(self, local_abastecido, yerba):
        venta = Venta("V-1", local_abastecido, Efectivo("0"))
        venta.agregar_detalle(yerba, 2)
        venta.agregar_detalle(yerba, 3)
        assert [(d.producto.codigo, d.cantidad) for d in venta.detalles] == [("P001", 5)]

    def test_strategy_cambia_el_total(self, local_abastecido, yerba):
        venta = Venta("V-1", local_abastecido, Efectivo("0.10"))
        venta.agregar_detalle(yerba, 2)
        assert venta.subtotal() == Decimal("2000.00")
        assert venta.calcular_total() == Decimal("1800.00")
        assert venta.ajuste() == Decimal("-200.00")
        venta.medio = Tarjeta("0.10")
        assert venta.calcular_total() == Decimal("2200.00")

    def test_confirmar_descuenta_stock_y_fija_cobro(self, local_abastecido, yerba, azucar):
        venta = venta_confirmada(local_abastecido, Tarjeta("0.10"), {yerba: 2, azucar: 4})
        assert local_abastecido.disponible(yerba.codigo) == 18
        assert local_abastecido.disponible(azucar.codigo) == 16
        assert venta.total_cobrado == Decimal("4400.00")
        assert venta.tasa_aplicada == Decimal("0.10")
        assert venta.medio_codigo == "TARJETA"
        assert venta.comprobante_numero == "CI-V-1"

    def test_reparto_del_total_con_residuo(self, cd_abastecido, local):  # RN-22
        a = Producto("A", "A", "C", "PRV01", "1", "1")
        b = Producto("B", "B", "C", "PRV01", "1", "1")
        c = Producto("C", "C", "C", "PRV01", "1", "1")
        for producto in (a, b, c):
            local.agregar_existencia(producto, cantidad=10)
        venta = venta_confirmada(local, Efectivo("0.3333"), {a: 1, b: 1, c: 1})
        # Subtotal 3.00, total 2.00: 2.00 / 3 = 0.666…; la última línea absorbe el centavo.
        importes = [d.importe_cobrado for d in venta.detalles]
        assert importes == [Decimal("0.67"), Decimal("0.67"), Decimal("0.66")]
        assert sum(importes) == venta.total_cobrado == Decimal("2.00")

    def test_reparto_proporcional(self, local_abastecido, yerba, azucar):
        venta = venta_confirmada(local_abastecido, Efectivo("0.10"), {yerba: 1, azucar: 1})
        assert [d.importe_cobrado for d in venta.detalles] == [Decimal("900.00"), Decimal("450.00")]

    def test_confirmada_es_inmutable(self, local_abastecido, yerba):  # RN-21
        venta = venta_confirmada(local_abastecido, Efectivo("0"), {yerba: 1})
        with pytest.raises(ValueError, match="confirmada"):
            venta.agregar_detalle(yerba, 1)
        with pytest.raises(ValueError, match="confirmada"):
            venta.medio = Tarjeta("0")
        with pytest.raises(ValueError, match="confirmada"):
            venta.confirmar()

    def test_precio_historico(self, local_abastecido, yerba):  # RN-21
        venta = venta_confirmada(local_abastecido, Efectivo("0"), {yerba: 1})
        yerba.precio = "5000"
        assert venta.detalles[0].precio_unitario == Decimal("1000.00")

    def test_venta_vacia(self, local_abastecido):  # RN-19
        with pytest.raises(ValueError, match="al menos un producto"):
            Venta("V-1", local_abastecido, Efectivo("0")).confirmar()

    def test_margen_por_linea(self, local_abastecido, yerba):
        venta = venta_confirmada(local_abastecido, Efectivo("0"), {yerba: 2})
        assert venta.detalles[0].margen() == Decimal("800.00")  # 2000 − 2 × 600


class TestDevolucion:
    def test_venta_no_confirmada(self, local_abastecido, yerba):  # RN-24
        venta = Venta("V-1", local_abastecido, Efectivo("0"))
        detalle = venta.agregar_detalle(yerba, 1)
        with pytest.raises(ValueError, match="ventas registradas"):
            Devolucion("D-1", venta, detalle, 1, True, "No le gustó")

    def test_linea_de_otra_venta(self, local_abastecido, yerba):  # RN-24
        venta = venta_confirmada(local_abastecido, Efectivo("0"), {yerba: 1}, "V-1")
        otra = venta_confirmada(local_abastecido, Efectivo("0"), {yerba: 1}, "V-2")
        with pytest.raises(ValueError, match="no pertenece"):
            Devolucion("D-1", venta, otra.detalles[0], 1, True, "Error")

    def test_motivo_obligatorio(self, local_abastecido, yerba):
        venta = venta_confirmada(local_abastecido, Efectivo("0"), {yerba: 1})
        with pytest.raises(ValueError, match="motivo"):
            Devolucion("D-1", venta, venta.detalles[0], 1, True, "")

    def test_acumulado_no_supera_lo_vendido(self, local_abastecido, yerba):  # RN-25
        venta = venta_confirmada(local_abastecido, Efectivo("0"), {yerba: 5})
        devolucion = Devolucion("D-2", venta, venta.detalles[0], 3, True, "Sobrante")
        with pytest.raises(ValueError, match="sólo se pueden devolver 2"):
            devolucion.confirmar(cantidad_ya_devuelta=3, importe_ya_devuelto="3000")

    def test_ejemplo_r2(self, local_abastecido, yerba):  # Documento maestro, sección 12
        venta = venta_confirmada(local_abastecido, Efectivo("0"), {yerba: 10})
        devolucion = Devolucion("D-1", venta, venta.detalles[0], 2, True, "Vencido")
        devolucion.confirmar(0, "0")
        assert devolucion.importe_reintegrado == Decimal("2000.00")
        assert devolucion.medio_codigo == "EFECTIVO"  # RN-26

    def test_ultimo_reintegro_absorbe_residuo(self, cd_abastecido, local):  # RN-26
        producto = Producto("X", "X", "C", "PRV01", "1", "1")
        local.agregar_existencia(producto, cantidad=10)
        venta = venta_confirmada(local, Efectivo("0"), {producto: 3})  # cobrado 3.00
        detalle = venta.detalles[0]
        primera = Devolucion("D-1", venta, detalle, 1, True, "a")
        primera.confirmar(0, "0")
        segunda = Devolucion("D-2", venta, detalle, 2, True, "b")
        segunda.confirmar(1, primera.importe_reintegrado)
        assert primera.importe_reintegrado + segunda.importe_reintegrado == Decimal("3.00")

    def test_reintegro_con_descuento_usa_lo_cobrado(self, local_abastecido, yerba):
        venta = venta_confirmada(local_abastecido, Efectivo("0.10"), {yerba: 4})  # cobrado 3600
        devolucion = Devolucion("D-1", venta, venta.detalles[0], 1, True, "Cambio")
        devolucion.confirmar(0, "0")
        assert devolucion.importe_reintegrado == Decimal("900.00")

    def test_apta_vuelve_al_disponible(self, local_abastecido, yerba):  # RN-27
        venta = venta_confirmada(local_abastecido, Efectivo("0"), {yerba: 5})
        Devolucion("D-1", venta, venta.detalles[0], 2, True, "Cambio").confirmar(0, "0")
        assert local_abastecido.disponible(yerba.codigo) == 17

    def test_no_apta_queda_fuera_de_venta(self, local_abastecido, yerba):  # RN-27
        venta = venta_confirmada(local_abastecido, Efectivo("0"), {yerba: 5})
        devolucion = Devolucion("D-1", venta, venta.detalles[0], 2, False, "Paquete roto")
        devolucion.confirmar(0, "0")
        assert local_abastecido.disponible(yerba.codigo) == 15
        assert devolucion.importe_reintegrado == Decimal("2000.00")

    def test_no_se_confirma_dos_veces(self, local_abastecido, yerba):
        venta = venta_confirmada(local_abastecido, Efectivo("0"), {yerba: 5})
        devolucion = Devolucion("D-1", venta, venta.detalles[0], 1, True, "Cambio")
        devolucion.confirmar(0, "0")
        with pytest.raises(ValueError, match="ya fue registrada"):
            devolucion.confirmar(1, devolucion.importe_reintegrado)
