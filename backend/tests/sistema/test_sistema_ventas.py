"""SistemaVentas de punta a punta, sobre SQLite en memoria con los datos de ejemplo."""

from decimal import Decimal

import pytest

from app.datos.conexion import ConexionSQLite
from app.inicializar import ARCHIVOS_EJEMPLO, CARPETA_EJEMPLO
from app.negocio.errores import Conflicto, ErrorImportacion, NoEncontrado
from app.negocio.sistema import SistemaVentas


@pytest.fixture
def conexion():
    conexion = ConexionSQLite(":memory:")
    conexion.crear_esquema()
    yield conexion
    conexion.cerrar()


@pytest.fixture
def sistema(conexion):
    """Datos de ejemplo cargados: CD con stock, tres locales vacíos, diez productos."""
    sistema = SistemaVentas(conexion, descuento_efectivo="0.10", recargo_tarjeta="0.10")
    for tipo, archivo in ARCHIVOS_EJEMPLO:
        sistema.importar_csv(tipo, CARPETA_EJEMPLO / archivo)
    return sistema


def disponible(sistema, sucursal, producto) -> int:
    filas = sistema.consultar_existencias(sucursal, producto)
    return filas[0]["disponible"] if filas else 0


def abastecer(sistema, destino="L01", producto="P001", cantidad=20, sufijo="1") -> dict:
    """Orden + bulto + recorrido completo hasta Verificado."""
    orden = sistema.crear_orden({"numero": f"O-{sufijo}", "necesidades": [
        {"destino_codigo": destino, "producto_codigo": producto, "cantidad": cantidad}]})
    detalle_id = orden["detalles"][0]["id"]
    sistema.preparar_bulto({"codigo": f"B-{sufijo}", "orden_numero": f"O-{sufijo}", "destino_codigo": destino,
                            "remito_numero": f"R-{sufijo}", "lineas": [{"detalle_id": detalle_id, "cantidad": cantidad}]})
    sistema.precintar(f"B-{sufijo}", f"PR-{sufijo}")
    sistema.despachar(f"B-{sufijo}")
    sistema.recibir(f"B-{sufijo}", True)
    return sistema.verificar(f"B-{sufijo}", True)


def venta(numero="V-1", local="L01", medio="EFECTIVO", items=(("P001", 2),), **extra) -> dict:
    return {"numero": numero, "local_codigo": local, "medio_codigo": medio,
            "items": [{"producto_codigo": p, "cantidad": c} for p, c in items], **extra}


class TestCatalogo:
    def test_datos_de_ejemplo(self, sistema):
        assert disponible(sistema, "CD", "P001") == 200
        assert len(sistema.consultar_catalogo("producto")) == 10
        assert sistema.consultar_existencias("L01", "P001")[0]["minimo"] == 10

    def test_proveedor_duplicado(self, sistema):  # RN-01
        with pytest.raises(Conflicto, match="Ya existe el proveedor"):
            sistema.guardar_catalogo("proveedor", {"codigo": "PRV01", "nombre": "Otro"})

    def test_editar_inexistente(self, sistema):
        with pytest.raises(NoEncontrado):
            sistema.guardar_catalogo("proveedor", {"codigo": "NADA", "nombre": "X"}, alta=False)

    def test_editar_producto(self, sistema):
        datos = sistema.consultar_catalogo("producto")[0] | {"precio": "4500"}
        sistema.guardar_catalogo("producto", datos, alta=False)
        assert sistema.consultar_catalogo("producto")[0]["precio"] == Decimal("4500.00")

    def test_producto_con_proveedor_inexistente_es_dato_invalido(self, sistema):
        with pytest.raises(ValueError, match="proveedor_codigo") as error:
            sistema.guardar_catalogo("producto", {"codigo": "P999", "nombre": "X", "categoria": "C",
                                                  "proveedor_codigo": "NADA", "precio": 1, "costo_referencia": 1})
        assert not isinstance(error.value, Conflicto)

    def test_un_solo_cd(self, sistema):  # RN-03
        with pytest.raises(Conflicto, match="sólo puede haber uno"):
            sistema.guardar_catalogo("sucursal", {"codigo": "CD2", "nombre": "Otro", "es_cd": True})

    def test_no_se_cambia_el_tipo_de_establecimiento(self, sistema):
        with pytest.raises(Conflicto):
            sistema.guardar_catalogo("sucursal", {"codigo": "L01", "nombre": "X", "es_cd": True}, alta=False)

    def test_configurar_minimo(self, sistema):
        resultado = sistema.configurar_minimo("L02", "P005", 25)
        assert (resultado["minimo"], resultado["faltante"]) == (25, 25)

    def test_medios_de_pago(self, sistema):
        assert [m["codigo"] for m in sistema.consultar_medios_pago()] == ["EFECTIVO", "TARJETA"]


class TestIngresos:
    def test_ingreso_suma_al_cd_y_actualiza_costo(self, sistema):  # RN-06, RN-07
        sistema.registrar_ingreso({"numero": "ING-9", "producto_codigo": "P001", "proveedor_codigo": "PRV01",
                                   "cantidad": 50, "costo_unitario": "3000"})
        assert disponible(sistema, "CD", "P001") == 250
        assert sistema.consultar_catalogo("producto")[0]["costo_referencia"] == Decimal("3000.00")

    def test_ingreso_repetido_no_duplica_stock(self, sistema):
        datos = {"numero": "ING-0001", "producto_codigo": "P001", "proveedor_codigo": "PRV01",
                 "cantidad": 50, "costo_unitario": "3000"}
        with pytest.raises(Conflicto):
            sistema.registrar_ingreso(datos)
        assert disponible(sistema, "CD", "P001") == 200


class TestLogistica:
    def test_recorrido_completo(self, sistema):
        bulto = abastecer(sistema, cantidad=20)
        assert bulto["estado"] == "VERIFICADO" and bulto["estado_remito"] == "VERIFICADO"
        assert [h["nuevo"] for h in bulto["historial"]] == [
            "PREPARADO", "PRECINTADO", "EN_TRANSITO", "RECIBIDO", "VERIFICADO"]
        assert disponible(sistema, "CD", "P001") == 180
        assert disponible(sistema, "L01", "P001") == 20

    def test_orden_consolidada(self, sistema):  # RN-09
        orden = sistema.crear_orden({"numero": "O-1", "necesidades": [
            {"destino_codigo": "L01", "producto_codigo": "P001", "cantidad": 5},
            {"destino_codigo": "L01", "producto_codigo": "P001", "cantidad": 7}]})
        assert [(d["solicitado"], d["pendiente"]) for d in orden["detalles"]] == [(12, 12)]

    def test_orden_al_cd_rechazada(self, sistema):  # RN-08
        with pytest.raises(ValueError, match="local"):
            sistema.crear_orden({"numero": "O-1", "necesidades": [
                {"destino_codigo": "CD", "producto_codigo": "P001", "cantidad": 5}]})

    def test_no_se_prepara_mas_que_lo_pendiente(self, sistema):  # RN-12
        orden = sistema.crear_orden({"numero": "O-1", "necesidades": [
            {"destino_codigo": "L01", "producto_codigo": "P001", "cantidad": 10}]})
        detalle_id = orden["detalles"][0]["id"]
        base = {"orden_numero": "O-1", "destino_codigo": "L01"}
        sistema.preparar_bulto(base | {"codigo": "B-1", "remito_numero": "R-1",
                                       "lineas": [{"detalle_id": detalle_id, "cantidad": 6}]})
        with pytest.raises(Conflicto, match="quedan 4"):
            sistema.preparar_bulto(base | {"codigo": "B-2", "remito_numero": "R-2",
                                           "lineas": [{"detalle_id": detalle_id, "cantidad": 5}]})
        assert disponible(sistema, "CD", "P001") == 194

    def test_falla_al_preparar_no_deja_rastros(self, sistema):
        orden = sistema.crear_orden({"numero": "O-1", "necesidades": [
            {"destino_codigo": "L01", "producto_codigo": "P006", "cantidad": 100}]})
        with pytest.raises(Conflicto, match="Stock insuficiente en el CD"):
            sistema.preparar_bulto({"codigo": "B-1", "orden_numero": "O-1", "destino_codigo": "L01",
                                    "remito_numero": "R-1",
                                    "lineas": [{"detalle_id": orden["detalles"][0]["id"], "cantidad": 100}]})
        assert disponible(sistema, "CD", "P006") == 60
        assert sistema.consultar_orden("O-1")["cerrada"] is False
        assert sistema.listar_bultos() == []

    def test_precinto_y_remito_unicos(self, sistema):  # RN-14
        abastecer(sistema, sufijo="1")
        orden = sistema.crear_orden({"numero": "O-2", "necesidades": [
            {"destino_codigo": "L02", "producto_codigo": "P002", "cantidad": 5}]})
        lineas = [{"detalle_id": orden["detalles"][0]["id"], "cantidad": 5}]
        with pytest.raises(Conflicto, match="remito"):
            sistema.preparar_bulto({"codigo": "B-2", "orden_numero": "O-2", "destino_codigo": "L02",
                                    "remito_numero": "R-1", "lineas": lineas})
        sistema.preparar_bulto({"codigo": "B-2", "orden_numero": "O-2", "destino_codigo": "L02",
                                "remito_numero": "R-2", "lineas": lineas})
        with pytest.raises(Conflicto, match="precinto"):
            sistema.precintar("B-2", "PR-1")

    def test_transicion_invalida_es_conflicto(self, sistema):  # RN-15
        abastecer(sistema)
        with pytest.raises(Conflicto):
            sistema.verificar("B-1", True)
        assert disponible(sistema, "L01", "P001") == 20

    def test_precinto_roto(self, sistema):  # RN-16, RN-17
        orden = sistema.crear_orden({"numero": "O-1", "necesidades": [
            {"destino_codigo": "L01", "producto_codigo": "P001", "cantidad": 10}]})
        sistema.preparar_bulto({"codigo": "B-1", "orden_numero": "O-1", "destino_codigo": "L01",
                                "remito_numero": "R-1",
                                "lineas": [{"detalle_id": orden["detalles"][0]["id"], "cantidad": 10}]})
        sistema.precintar("B-1", "PR-1")
        sistema.despachar("B-1")
        bulto = sistema.recibir("B-1", False, "Precinto cortado")
        assert bulto["estado"] == "RECHAZADO" and bulto["acciones_permitidas"] == []
        assert disponible(sistema, "L01", "P001") == 0

    def test_bulto_inexistente(self, sistema):
        with pytest.raises(NoEncontrado):
            sistema.despachar("NO-EXISTE")


class TestVentas:
    def test_cotizar_no_guarda_ni_reserva(self, sistema):
        abastecer(sistema)
        cotizacion = sistema.cotizar_venta(venta(medio="TARJETA"))
        assert cotizacion["subtotal"] == Decimal("8400.00")
        assert cotizacion["ajuste"] == Decimal("840.00")
        assert cotizacion["total"] == Decimal("9240.00")
        assert disponible(sistema, "L01", "P001") == 20
        assert sistema.listar_ventas() == []

    def test_no_se_vende_lo_recibido_sin_verificar(self, sistema):  # RN-17, RN-20
        orden = sistema.crear_orden({"numero": "O-1", "necesidades": [
            {"destino_codigo": "L01", "producto_codigo": "P001", "cantidad": 10}]})
        sistema.preparar_bulto({"codigo": "B-1", "orden_numero": "O-1", "destino_codigo": "L01",
                                "remito_numero": "R-1",
                                "lineas": [{"detalle_id": orden["detalles"][0]["id"], "cantidad": 10}]})
        sistema.precintar("B-1", "PR-1")
        sistema.despachar("B-1")
        sistema.recibir("B-1", True)
        with pytest.raises(Conflicto, match="Stock insuficiente"):
            sistema.confirmar_venta(venta())

    def test_confirmar_venta(self, sistema):
        abastecer(sistema)
        resultado = sistema.confirmar_venta(venta(total_esperado="7560.00"))
        assert resultado["total_cobrado"] == Decimal("7560.00")
        assert resultado["comprobante_numero"] == "CI-V-1"
        assert disponible(sistema, "L01", "P001") == 18

    def test_total_cambiado_no_guarda(self, sistema):  # RN-23
        abastecer(sistema)
        with pytest.raises(Conflicto, match="Vuelva a cotizar"):
            sistema.confirmar_venta(venta(total_esperado="7000.00"))
        assert sistema.listar_ventas() == []
        assert disponible(sistema, "L01", "P001") == 20

    def test_numero_repetido(self, sistema):
        abastecer(sistema)
        sistema.confirmar_venta(venta())
        with pytest.raises(Conflicto, match="Ya existe la venta"):
            sistema.confirmar_venta(venta())
        assert disponible(sistema, "L01", "P001") == 18

    def test_medio_desconocido(self, sistema):
        abastecer(sistema)
        with pytest.raises(ValueError, match="medio_codigo"):
            sistema.confirmar_venta(venta(medio="CHEQUE"))

    def test_devoluciones(self, sistema):  # RN-24 a RN-27
        abastecer(sistema)
        confirmada = sistema.confirmar_venta(venta(items=(("P001", 5),)))  # 5 × 4200 − 10 % = 18900
        linea = confirmada["lineas"][0]["id"]
        base = {"venta_numero": "V-1", "detalle_id": linea}

        primera = sistema.devolver(base | {"numero": "D-1", "cantidad": 2, "apta_reventa": True, "motivo": "Cambio"})
        assert primera["importe_reintegrado"] == Decimal("7560.00")
        assert primera["medio_codigo"] == "EFECTIVO"
        sistema.devolver(base | {"numero": "D-2", "cantidad": 3, "apta_reventa": False, "motivo": "Roto"})

        with pytest.raises(Conflicto, match="sólo se pueden devolver 0"):
            sistema.devolver(base | {"numero": "D-3", "cantidad": 1, "apta_reventa": True, "motivo": "X"})

        detalle = sistema.consultar_venta("V-1")["lineas"][0]
        assert (detalle["cantidad_devuelta"], detalle["cantidad_restante"]) == (5, 0)
        assert detalle["importe_devuelto"] == Decimal("18900.00")
        assert disponible(sistema, "L01", "P001") == 15 + 2  # sólo lo apto

    def test_devolucion_de_venta_inexistente(self, sistema):  # RN-24
        with pytest.raises(NoEncontrado):
            sistema.devolver({"numero": "D-1", "venta_numero": "V-99", "detalle_id": 1, "cantidad": 1,
                              "apta_reventa": True, "motivo": "X"})


class TestImportacionCSV:
    def test_errores_por_fila_sin_importacion_parcial(self, sistema, tmp_path):  # RN-28
        archivo = tmp_path / "productos.csv"
        archivo.write_text(
            "codigo,nombre,categoria,proveedor_codigo,precio,costo_referencia\n"
            "P100,Galletitas,Almacén,PRV01,900,500\n"
            "P101,Arroz,Almacén,NO_EXISTE,800,400\n"
            "P102,,Almacén,PRV01,800,400\n"
            "P100,Repetido,Almacén,PRV01,1,1\n",
            encoding="utf-8",
        )
        with pytest.raises(ErrorImportacion) as error:
            sistema.importar_csv("productos", archivo)
        assert [(e["fila"], e["campo"]) for e in error.value.errores] == [
            (3, "proveedor_codigo"), (4, "nombre"), (5, None)]
        assert len(sistema.consultar_catalogo("producto")) == 10  # no entró ni la fila válida

    def test_separador_punto_y_coma(self, sistema, tmp_path):
        archivo = tmp_path / "proveedores.csv"
        archivo.write_text("codigo;nombre\nPRV09;Proveedor con punto y coma\n", encoding="utf-8-sig")
        assert sistema.importar_csv("proveedores", archivo)["filas_importadas"] == 1

    def test_encabezado_invalido(self, sistema, tmp_path):
        archivo = tmp_path / "proveedores.csv"
        archivo.write_text("code,name\nPRV09,X\n", encoding="utf-8")
        with pytest.raises(ErrorImportacion) as error:
            sistema.importar_csv("proveedores", archivo)
        assert error.value.errores[0]["fila"] == 1

    def test_archivo_vacio(self, sistema, tmp_path):
        archivo = tmp_path / "vacio.csv"
        archivo.write_text("", encoding="utf-8")
        with pytest.raises(ErrorImportacion):
            sistema.importar_csv("proveedores", archivo)

    def test_columnas_de_mas_en_una_fila(self, sistema, tmp_path):
        archivo = tmp_path / "proveedores.csv"
        archivo.write_text("codigo,nombre\nPRV09,X,sobra\n", encoding="utf-8")
        with pytest.raises(ErrorImportacion) as error:
            sistema.importar_csv("proveedores", archivo)
        assert error.value.errores[0]["fila"] == 2
