"""Casos que fallaban antes de las correcciones de importes y encapsulamiento."""
from decimal import Decimal

import pytest

from app.negocio.modelos import Producto, Sucursal, Venta, Devolucion, OrdenReposicion, Bulto
from app.negocio.pagos import Efectivo, Tarjeta
from app.negocio.errores import Conflicto


def armar_venta(precios, cantidades=None, medio=None):
    local = Sucursal("L", "Local")
    venta = Venta("V", local, medio or Efectivo("0.10"))
    for i, precio in enumerate(precios):
        producto = Producto(f"P{i:02}", "Producto", "Categoría", "PR", precio, "0.01")
        cantidad = cantidades[i] if cantidades else 1
        local.agregar_existencia(producto, cantidad)
        venta.agregar_detalle(producto, cantidad)
    return venta


def test_veinte_lineas_de_cinco_centavos_no_generan_importes_negativos():
    venta = armar_venta(["0.05"] * 20)
    venta.confirmar()
    importes = [d.importe_cobrado for d in venta.detalles]
    assert venta.total_cobrado == sum(importes) == Decimal("0.90")
    assert importes.count(Decimal("0.05")) == 10
    assert importes.count(Decimal("0.04")) == 10


def test_desempate_por_codigo_no_depende_del_orden_de_carga():
    local = Sucursal("L", "Local")
    productos = [Producto(c, c, "C", "PR", "1", "1") for c in ("C", "B", "A")]
    for p in productos:
        local.agregar_existencia(p, 2)
    resultados = []
    for orden in (productos, list(reversed(productos))):
        venta = Venta("V", local, Efectivo("0.3333"))
        for p in orden:
            venta.agregar_detalle(p, 1)
        venta.confirmar()
        resultados.append({d.producto.codigo: d.importe_cobrado for d in venta.detalles})
    assert resultados[0] == resultados[1] == {
        "A": Decimal("0.67"), "B": Decimal("0.67"), "C": Decimal("0.66"),
    }


@pytest.mark.parametrize("precio", ["0.01", "0.05", "0.99", "1.01"])
@pytest.mark.parametrize("medio", [Efectivo("0.10"), Tarjeta("0.10"), Efectivo("0.99")])
def test_devoluciones_unitarias_completas_sin_exceder_el_cobro(precio, medio):
    for cantidad in range(1, 41):
        venta = armar_venta([precio], [cantidad], medio)
        venta.confirmar()
        reintegrado = Decimal("0")
        for i in range(cantidad):
            devolucion = Devolucion(f"D{i}", venta, venta.detalles[0], 1, False, "Cambio")
            devolucion.confirmar(i, reintegrado)
            assert devolucion.importe_reintegrado >= 0
            reintegrado += devolucion.importe_reintegrado
            assert reintegrado <= venta.total_cobrado
        assert reintegrado == venta.total_cobrado


def test_devoluciones_anteriores_con_redondeo_excesivo_se_conservan():
    venta = armar_venta(["0.05"], [20])
    venta.confirmar()
    # El algoritmo viejo ya reintegró 18 * 0.05: aún quedan dos unidades.
    for cantidad_anterior in (18, 19):
        devolucion = Devolucion(str(cantidad_anterior), venta, venta.detalles[0], 1, True, "Cambio")
        devolucion.confirmar(cantidad_anterior, Decimal("0.90"))
        assert devolucion.importe_reintegrado == Decimal("0.00")
    assert venta.local.disponible("P00") == 2


def test_state_no_muta_bulto_por_llamada_directa_y_verificar_acredita_una_vez():
    p = Producto("P", "Producto", "C", "PR", "1", "1")
    cd, local = Sucursal("CD", "CD", True), Sucursal("L", "Local")
    cd.agregar_existencia(p, 5)
    orden = OrdenReposicion("O", cd)
    linea = orden.agregar_necesidad(local, p, 5)
    bulto = Bulto("B", orden, local, "R", [(linea, 5)])
    bulto.precintar("S")
    bulto.despachar()
    bulto.recibir(True)
    estado = bulto.estado
    estado.verificar(bulto, True)
    estado.verificar(bulto, True)
    assert bulto.estado.nombre() == "RECIBIDO"
    assert local.disponible("P") == 0
    with pytest.raises(ValueError):
        bulto.verificar(False, "")
    assert len(bulto.historial) == 4
    assert not hasattr(bulto, "acreditar_destino")
    assert not hasattr(bulto, "cambiar_estado")
    bulto.verificar(True)
    with pytest.raises(Conflicto):
        bulto.verificar(True)
    assert local.disponible("P") == 5
    assert len(bulto.historial) == 5
