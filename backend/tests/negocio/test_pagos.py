"""Patrón Strategy: medios de pago."""

from decimal import Decimal

import pytest

from app.negocio.pagos import Efectivo, MedioPago, Tarjeta, crear_medio_pago


def test_efectivo_aplica_descuento():
    assert Efectivo("0.10").calcular_total(Decimal("1000")) == Decimal("900.00")


def test_tarjeta_aplica_recargo():
    assert Tarjeta("0.10").calcular_total(Decimal("1000")) == Decimal("1100.00")


def test_redondeo_a_centavos():
    assert Efectivo("0.10").calcular_total(Decimal("333.33")) == Decimal("300.00")


@pytest.mark.parametrize("tasa", ["1", "1.5", "-0.01"])
def test_descuento_fuera_de_rango(tasa):
    with pytest.raises(ValueError):
        Efectivo(tasa)


def test_descuento_cero_es_valido():
    assert Efectivo("0").calcular_total(Decimal("100")) == Decimal("100.00")


def test_recargo_negativo_es_invalido():
    with pytest.raises(ValueError):
        Tarjeta("-0.05")


def test_tasa_no_numerica():
    with pytest.raises(ValueError):
        Tarjeta("diez")


def test_medio_pago_es_abstracto():
    with pytest.raises(TypeError):
        MedioPago("X")


def test_crear_medio_desde_codigo():
    medio = crear_medio_pago("TARJETA", "0.15")
    assert isinstance(medio, Tarjeta)
    assert medio.tasa == Decimal("0.15")


def test_crear_medio_desconocido():
    with pytest.raises(ValueError):
        crear_medio_pago("CHEQUE", "0")
