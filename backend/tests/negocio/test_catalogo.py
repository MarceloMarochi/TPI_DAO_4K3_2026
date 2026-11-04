"""Catálogo y stock: Producto, Sucursal, Existencia e IngresoStock."""

from decimal import Decimal

import pytest

from app.negocio.modelos import IngresoStock, Producto, Sucursal


class TestProducto:
    def test_crea_con_importes_decimales(self, yerba):
        assert yerba.precio == Decimal("1000.00")
        assert yerba.costo_referencia == Decimal("600.00")

    @pytest.mark.parametrize("precio", ["0", "-1", "abc"])
    def test_precio_invalido(self, precio):
        with pytest.raises(ValueError):
            Producto("P9", "X", "Cat", "PRV", precio, "1")

    def test_nombre_vacio(self):
        with pytest.raises(ValueError):
            Producto("P9", "  ", "Cat", "PRV", "1", "1")

    def test_codigo_no_se_modifica(self, yerba):
        with pytest.raises(AttributeError):
            yerba.codigo = "OTRO"

    def test_setter_valida(self, yerba):
        with pytest.raises(ValueError):
            yerba.precio = 0
        assert yerba.precio == Decimal("1000.00")


class TestSucursalYExistencia:
    def test_existencia_unica_por_producto(self, local, yerba):  # RN-04
        local.agregar_existencia(yerba)
        with pytest.raises(ValueError):
            local.agregar_existencia(yerba)

    def test_lista_de_existencias_es_copia(self, local, yerba):
        local.existencias.append("intruso")
        assert local.existencias == []

    def test_retirar_mas_que_disponible(self, local, yerba):
        existencia = local.agregar_existencia(yerba, cantidad=5)
        with pytest.raises(ValueError, match="Stock insuficiente"):
            existencia.retirar(6)
        assert existencia.cantidad == 5

    def test_disponible_no_se_edita_directamente(self, local, yerba):  # RN-05
        existencia = local.agregar_existencia(yerba)
        with pytest.raises(AttributeError):
            existencia.cantidad = 50

    def test_faltante_para_el_minimo(self, local, yerba):
        existencia = local.agregar_existencia(yerba, cantidad=4, minimo=10)
        assert existencia.faltante() == 6
        assert existencia.bajo_minimo()

    def test_minimo_negativo(self, local, yerba):
        existencia = local.agregar_existencia(yerba)
        with pytest.raises(ValueError):
            existencia.minimo = -1

    def test_disponible_de_producto_sin_existencia(self, local):
        assert local.disponible("NO_EXISTE") == 0


class TestIngresoStock:
    def test_suma_al_cd_y_actualiza_costo(self, cd, yerba):  # RN-06, RN-07
        IngresoStock("I-1", yerba, "PRV01", 20, "650").aplicar(cd)
        assert cd.disponible(yerba.codigo) == 20
        assert yerba.costo_referencia == Decimal("650.00")

    def test_no_se_registra_en_un_local(self, local, yerba):  # RN-06
        with pytest.raises(ValueError, match="Centro de Distribución"):
            IngresoStock("I-1", yerba, "PRV01", 20, "650").aplicar(local)

    @pytest.mark.parametrize("cantidad, costo", [(0, "10"), (5, "0"), (-1, "10")])
    def test_cantidad_y_costo_positivos(self, yerba, cantidad, costo):
        with pytest.raises(ValueError):
            IngresoStock("I-1", yerba, "PRV01", cantidad, costo)

    def test_importe(self, yerba):
        assert IngresoStock("I-1", yerba, "PRV01", 3, "10.50").importe() == Decimal("31.50")
