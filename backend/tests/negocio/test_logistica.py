"""Reposición y ciclo de vida del bulto (patrón State)."""

import pytest
from app.negocio.errores import Conflicto

from app.negocio.estados import EnTransito, Verificado, estado_desde_nombre
from app.negocio.modelos import Bulto, OrdenReposicion

from .conftest import abastecer_local, numero, preparar_bulto


class TestOrdenReposicion:
    def test_origen_debe_ser_cd(self, local):  # RN-08
        with pytest.raises(ValueError, match="CD"):
            OrdenReposicion("O-1", local)

    def test_destino_debe_ser_local(self, cd, yerba):  # RN-08
        orden = OrdenReposicion("O-1", cd)
        with pytest.raises(ValueError, match="local"):
            orden.agregar_necesidad(cd, yerba, 5)

    def test_consolida_producto_y_destino(self, cd, local, local_norte, yerba):  # RN-09
        orden = OrdenReposicion("O-1", cd)
        orden.agregar_necesidad(local, yerba, 5)
        orden.agregar_necesidad(local, yerba, 3)
        orden.agregar_necesidad(local_norte, yerba, 2)
        cantidades = {(d.destino.codigo, d.producto.codigo): d.cantidad for d in orden.detalles}
        assert cantidades == {("L01", "P001"): 8, ("L02", "P001"): 2}

    def test_orden_vacia_no_valida(self, cd):
        with pytest.raises(ValueError):
            OrdenReposicion("O-1", cd).validar()


class TestPreparacion:
    def test_bulto_nuevo_queda_preparado(self, cd_abastecido, local, yerba):
        bulto = preparar_bulto(cd_abastecido, local, {yerba: 10})
        assert bulto.estado.nombre() == "PREPARADO"
        assert bulto.orden.cerrada  # RN-10
        assert [(c.anterior, c.nuevo) for c in bulto.historial] == [(None, "PREPARADO")]

    def test_descuenta_el_cd_una_sola_vez(self, cd_abastecido, local, yerba):  # RN-13
        bulto = preparar_bulto(cd_abastecido, local, {yerba: 10})
        assert cd_abastecido.disponible(yerba.codigo) == 90
        bulto.precintar("PR-1")
        bulto.despachar()
        assert cd_abastecido.disponible(yerba.codigo) == 90

    def test_stock_insuficiente_no_descuenta_nada(self, cd_abastecido, local, yerba, azucar):  # RN-13
        with pytest.raises(ValueError, match="Stock insuficiente en el CD"):
            preparar_bulto(cd_abastecido, local, {yerba: 10, azucar: 500})
        assert cd_abastecido.disponible(yerba.codigo) == 100

    def test_orden_cerrada_no_admite_necesidades(self, cd_abastecido, local, yerba):  # RN-10
        bulto = preparar_bulto(cd_abastecido, local, {yerba: 10})
        with pytest.raises(ValueError, match="no admite cambios"):
            bulto.orden.agregar_necesidad(local, yerba, 1)

    def test_bulto_sin_contenido(self, cd_abastecido, local):
        orden = OrdenReposicion("O-1", cd_abastecido)
        with pytest.raises(ValueError, match="contenido"):
            Bulto("B-1", orden, local, "R-1", [])

    def test_linea_de_otro_destino(self, cd_abastecido, local, local_norte, yerba):  # RN-11
        orden = OrdenReposicion("O-1", cd_abastecido)
        linea_norte = orden.agregar_necesidad(local_norte, yerba, 5)
        with pytest.raises(ValueError, match="es para L02"):
            Bulto("B-1", orden, local, "R-1", [(linea_norte, 5)])

    def test_linea_de_otra_orden(self, cd_abastecido, local, yerba):  # RN-11
        orden = OrdenReposicion("O-1", cd_abastecido)
        otra = OrdenReposicion("O-2", cd_abastecido)
        linea_ajena = otra.agregar_necesidad(local, yerba, 5)
        with pytest.raises(ValueError, match="pertenecer a su orden"):
            Bulto("B-1", orden, local, "R-1", [(linea_ajena, 5)])

    def test_no_supera_lo_pedido(self, cd_abastecido, local, yerba):  # RN-12
        orden = OrdenReposicion("O-1", cd_abastecido)
        linea = orden.agregar_necesidad(local, yerba, 5)
        with pytest.raises(ValueError, match="se pidieron 5"):
            Bulto("B-1", orden, local, "R-1", [(linea, 6)])


class TestCicloDelBulto:
    def test_recorrido_completo(self, cd_abastecido, local, yerba):
        bulto = preparar_bulto(cd_abastecido, local, {yerba: 10})
        bulto.precintar("PR-1")
        bulto.despachar()
        bulto.recibir(intacto=True)
        assert local.disponible(yerba.codigo) == 0  # RN-17: recibido no habilita la venta
        assert bulto.estado_remito() == "PENDIENTE"

        bulto.verificar(conforme=True)

        assert local.disponible(yerba.codigo) == 10
        assert bulto.estado_remito() == "VERIFICADO"
        assert bulto.precinto_numero == "PR-1"
        assert bulto.precinto_intacto is True
        assert [c.nuevo for c in bulto.historial] == [
            "PREPARADO", "PRECINTADO", "EN_TRANSITO", "RECIBIDO", "VERIFICADO"
        ]
        assert [c.secuencia for c in bulto.historial] == [1, 2, 3, 4, 5]

    def test_precinto_roto_rechaza(self, cd_abastecido, local, yerba):
        bulto = preparar_bulto(cd_abastecido, local, {yerba: 10})
        bulto.precintar("PR-1")
        bulto.despachar()
        bulto.recibir(intacto=False, motivo="Precinto cortado")
        assert bulto.estado.nombre() == "RECHAZADO"
        assert bulto.estado_remito() == "RECHAZADO"
        assert bulto.historial[-1].motivo == "Precinto cortado"
        assert local.disponible(yerba.codigo) == 0
        assert cd_abastecido.disponible(yerba.codigo) == 90  # no vuelve solo al CD

    def test_precinto_roto_exige_motivo(self, cd_abastecido, local, yerba):  # RN-16
        bulto = preparar_bulto(cd_abastecido, local, {yerba: 10})
        bulto.precintar("PR-1")
        bulto.despachar()
        with pytest.raises(ValueError, match="motivo"):
            bulto.recibir(intacto=False)
        assert bulto.estado.nombre() == "EN_TRANSITO"
        assert bulto.precinto_intacto is None

    def test_verificacion_no_conforme(self, cd_abastecido, local, yerba):
        bulto = preparar_bulto(cd_abastecido, local, {yerba: 10})
        bulto.precintar("PR-1")
        bulto.despachar()
        bulto.recibir(intacto=True)
        with pytest.raises(ValueError, match="motivo"):  # RN-16
            bulto.verificar(conforme=False)
        bulto.verificar(conforme=False, motivo="Faltan 2 unidades")
        assert bulto.estado.nombre() == "RECHAZADO"
        assert local.disponible(yerba.codigo) == 0

    @pytest.mark.parametrize("operacion", [
        lambda b: b.despachar(),
        lambda b: b.recibir(True),
        lambda b: b.verificar(True),
    ])
    def test_operaciones_invalidas_desde_preparado(self, cd_abastecido, local, yerba, operacion):  # RN-15
        bulto = preparar_bulto(cd_abastecido, local, {yerba: 10})
        with pytest.raises(ValueError, match="estado PREPARADO"):
            operacion(bulto)
        assert len(bulto.historial) == 1

    def test_verificar_dos_veces_no_acredita_dos_veces(self, cd_abastecido, local, yerba):
        bulto = abastecer_local(cd_abastecido, local, {yerba: 10})
        with pytest.raises(ValueError):
            bulto.verificar(conforme=True)
        assert local.disponible(yerba.codigo) == 10

    @pytest.mark.parametrize("operacion", ["precintar", "despachar", "recibir", "verificar"])
    def test_estados_finales_no_admiten_operaciones(self, cd_abastecido, local, yerba, operacion):
        bulto = abastecer_local(cd_abastecido, local, {yerba: 10})
        argumentos = {"precintar": ("X",), "despachar": (), "recibir": (True,), "verificar": (True,)}
        with pytest.raises(ValueError):
            getattr(bulto, operacion)(*argumentos[operacion])

    def test_acciones_permitidas_por_estado(self, cd_abastecido, local, yerba):
        bulto = preparar_bulto(cd_abastecido, local, {yerba: 10})
        acciones = [bulto.acciones_permitidas()]
        bulto.precintar("PR-1"); acciones.append(bulto.acciones_permitidas())
        bulto.despachar(); acciones.append(bulto.acciones_permitidas())
        bulto.recibir(True); acciones.append(bulto.acciones_permitidas())
        bulto.verificar(True); acciones.append(bulto.acciones_permitidas())
        assert acciones == [["precintar"], ["despachar"], ["recibir"], ["verificar"], []]

    def test_no_se_puede_saltear_estados(self, cd_abastecido, local, yerba):
        bulto = preparar_bulto(cd_abastecido, local, {yerba: 10})
        with pytest.raises(AttributeError):
            bulto.cambiar_estado(Verificado())
        with pytest.raises(Conflicto):
            bulto.verificar(True)

    def test_no_se_acredita_stock_fuera_de_recibido(self, cd_abastecido, local, yerba):
        bulto = preparar_bulto(cd_abastecido, local, {yerba: 10})
        with pytest.raises(AttributeError):
            bulto.acreditar_destino()
        assert local.disponible(yerba.codigo) == 0


class TestHistorialInmutable:  # RN-18
    def test_cambio_estado_no_se_modifica(self, cd_abastecido, local, yerba):
        cambio = preparar_bulto(cd_abastecido, local, {yerba: 1}).historial[0]
        with pytest.raises(AttributeError):
            cambio._nuevo = "VERIFICADO"
        with pytest.raises(AttributeError):
            cambio.motivo = "otro"

    def test_historial_devuelto_es_copia(self, cd_abastecido, local, yerba):
        bulto = preparar_bulto(cd_abastecido, local, {yerba: 1})
        bulto.historial.clear()
        assert len(bulto.historial) == 1


class TestRestauracion:
    def test_restaurar_no_repite_efectos(self, cd_abastecido, local, yerba):
        original = preparar_bulto(cd_abastecido, local, {yerba: 10})
        original.precintar("PR-1")
        original.despachar()

        copia = Bulto.restaurar(
            original.codigo, original.orden, original.destino, original.remito_numero,
            original.detalles, estado_desde_nombre("EN_TRANSITO"), original.historial,
            precinto_numero="PR-1",
        )
        assert isinstance(copia.estado, EnTransito)
        assert cd_abastecido.disponible(yerba.codigo) == 90
        copia.recibir(True)
        assert copia.historial[-1].secuencia == 4

    def test_restaurar_con_historial_incoherente(self, cd_abastecido, local, yerba):
        original = preparar_bulto(cd_abastecido, local, {yerba: 10})
        with pytest.raises(ValueError, match="no coincide"):
            Bulto.restaurar(
                original.codigo, original.orden, original.destino, original.remito_numero,
                original.detalles, estado_desde_nombre("VERIFICADO"), original.historial,
            )

    def test_estado_desconocido(self):
        with pytest.raises(ValueError):
            estado_desde_nombre("PERDIDO")


def test_varios_bultos_por_orden(cd_abastecido, local, yerba):
    orden = OrdenReposicion(numero("O"), cd_abastecido)
    linea = orden.agregar_necesidad(local, yerba, 10)
    Bulto(numero("B"), orden, local, numero("R"), [(linea, 6)])
    Bulto(numero("B"), orden, local, numero("R"), [(linea, 4)])
    assert linea.pendiente(asignado=10) == 0
    assert cd_abastecido.disponible(yerba.codigo) == 90
