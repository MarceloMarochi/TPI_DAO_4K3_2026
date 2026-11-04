"""Datos de prueba compartidos por los tests del dominio (sin base de datos)."""

import itertools

import pytest

from app.negocio.modelos import Bulto, IngresoStock, OrdenReposicion, Producto, Sucursal

_numeros = itertools.count(1)


def numero(prefijo: str) -> str:
    return f"{prefijo}-{next(_numeros):04d}"


@pytest.fixture
def cd():
    return Sucursal("CD", "Centro de Distribución", es_cd=True)


@pytest.fixture
def local():
    return Sucursal("L01", "Local Centro")


@pytest.fixture
def local_norte():
    return Sucursal("L02", "Local Norte")


@pytest.fixture
def yerba():
    return Producto("P001", "Yerba 1 kg", "Almacén", "PRV01", "1000", "600")


@pytest.fixture
def azucar():
    return Producto("P002", "Azúcar 1 kg", "Almacén", "PRV01", "500", "300")


@pytest.fixture
def cd_abastecido(cd, yerba, azucar):
    """CD con 100 unidades de cada producto."""
    IngresoStock(numero("I"), yerba, "PRV01", 100, "600").aplicar(cd)
    IngresoStock(numero("I"), azucar, "PRV01", 100, "300").aplicar(cd)
    return cd


def preparar_bulto(cd, destino, contenido: dict) -> Bulto:
    """Arma una orden y un bulto con {producto: cantidad} para un destino."""
    orden = OrdenReposicion(numero("O"), cd)
    lineas = [(orden.agregar_necesidad(destino, producto, cantidad), cantidad)
              for producto, cantidad in contenido.items()]
    return Bulto(numero("B"), orden, destino, numero("R"), lineas)


def abastecer_local(cd, destino, contenido: dict) -> Bulto:
    """Recorre todo el circuito logístico hasta dejar la mercadería disponible en el local."""
    bulto = preparar_bulto(cd, destino, contenido)
    bulto.precintar(numero("PR"))
    bulto.despachar()
    bulto.recibir(intacto=True)
    bulto.verificar(conforme=True)
    return bulto
