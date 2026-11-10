"""Reportes R1 a R4 con los ejemplos del documento maestro (sección 12) y exportación PDF.

Un reloj controlable reemplaza la fecha del servidor para ubicar operaciones en distintos días.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.datos.conexion import ConexionSQLite
from app.inicializar import ARCHIVOS_EJEMPLO, CARPETA_EJEMPLO, inicializar
from app.main import create_app
from app.negocio import comunes, bultos, servicio_reportes
from app.negocio.comunes import ZONA_HORARIA
from app.negocio.errores import NoEncontrado
from app.negocio.sistema import SistemaVentas
from app.presentacion.exportador_pdf import ExportadorPDF, formatear_importe

DIA_1 = date(2026, 10, 1)


class Reloj:
    def __init__(self):
        self.actual = datetime(2026, 10, 1, 10, 0, tzinfo=ZONA_HORARIA)

    def __call__(self):
        self.actual += timedelta(seconds=1)  # cada consulta avanza un segundo: fechas siempre crecientes
        return self.actual

    def ir_al_dia(self, dia: date):
        self.actual = datetime.combine(dia, datetime.min.time(), tzinfo=ZONA_HORARIA).replace(hour=10)


@pytest.fixture
def reloj(monkeypatch):
    reloj = Reloj()
    for modulo in (comunes, bultos, servicio_reportes):
        monkeypatch.setattr(modulo, "ahora", reloj)
    return reloj


@pytest.fixture
def sistema(reloj):
    """Datos de ejemplo + producto PX (precio 1000, costo 600). Tasas en cero para que los importes sean exactos."""
    conexion = ConexionSQLite(":memory:")
    conexion.crear_esquema()
    sistema = SistemaVentas(conexion, descuento_efectivo="0", recargo_tarjeta="0")
    for tipo, archivo in ARCHIVOS_EJEMPLO:
        sistema.importar_csv(tipo, CARPETA_EJEMPLO / archivo)
    sistema.guardar_catalogo("producto", {"codigo": "PX", "nombre": "Producto X", "categoria": "Prueba",
                                          "proveedor_codigo": "PRV01", "precio": "1000", "costo_referencia": "600"})
    sistema.registrar_ingreso({"numero": "ING-PX", "producto_codigo": "PX", "proveedor_codigo": "PRV01",
                               "cantidad": 2000, "costo_unitario": "600"})
    yield sistema
    conexion.cerrar()


_contador = iter(range(1, 10_000))


def bulto(sistema, destino, producto, cantidad, hasta="VERIFICADO", motivo="") -> str:
    """Crea orden y bulto y lo avanza hasta el estado pedido. Devuelve el código del bulto."""
    n = next(_contador)
    orden = sistema.crear_orden({"numero": f"O-{n}", "necesidades": [
        {"destino_codigo": destino, "producto_codigo": producto, "cantidad": cantidad}]})
    codigo = f"B-{n}"
    sistema.preparar_bulto({"codigo": codigo, "orden_numero": f"O-{n}", "destino_codigo": destino,
                            "remito_numero": f"R-{n}",
                            "lineas": [{"detalle_id": orden["detalles"][0]["id"], "cantidad": cantidad}]})
    pasos = {
        "PRECINTADO": [lambda: sistema.precintar(codigo, f"PR-{n}")],
        "EN_TRANSITO": [lambda: sistema.despachar(codigo)],
        "RECIBIDO": [lambda: sistema.recibir(codigo, True)],
        "VERIFICADO": [lambda: sistema.verificar(codigo, True)],
        "RECHAZADO_PRECINTO": [lambda: sistema.recibir(codigo, False, motivo)],
        "RECHAZADO_CONTROL": [lambda: sistema.recibir(codigo, True), lambda: sistema.verificar(codigo, False, motivo)],
    }
    orden_estados = ["PRECINTADO", "EN_TRANSITO", "RECIBIDO", "VERIFICADO"]
    if hasta.startswith("RECHAZADO"):
        recorrido = ["PRECINTADO", "EN_TRANSITO", hasta]
    else:
        recorrido = orden_estados[: orden_estados.index(hasta) + 1] if hasta != "PREPARADO" else []
    for estado in recorrido:
        for paso in pasos[estado]:
            paso()
    return codigo


def vender(sistema, numero, medio, cantidad, producto="PX", local="L01") -> int:
    datos = {"numero": numero, "local_codigo": local, "medio_codigo": medio,
             "items": [{"producto_codigo": producto, "cantidad": cantidad}]}
    total = sistema.cotizar_venta(datos)["total"]
    venta = sistema.confirmar_venta(datos | {"total_esperado": total})
    return venta["lineas"][0]["id"]


def devolver(sistema, numero, venta, linea, cantidad, apta=True):
    sistema.devolver({"numero": numero, "venta_numero": venta, "detalle_id": linea, "cantidad": cantidad,
                      "apta_reventa": apta, "motivo": "Prueba"})


def fila(filas, **criterio) -> dict:
    return next(f for f in filas if all(f[k] == v for k, v in criterio.items()))


# ---------------------------------------------------------------------------
# R1 Ventas e ingresos
# ---------------------------------------------------------------------------


class TestR1Ventas:
    def test_ejemplo_del_documento(self, sistema):
        bulto(sistema, "L01", "PX", 400)
        linea_1 = vender(sistema, "V-1", "EFECTIVO", 180)
        linea_2 = vender(sistema, "V-2", "TARJETA", 165)
        devolver(sistema, "D-1", "V-1", linea_1, 10)
        devolver(sistema, "D-2", "V-2", linea_2, 5)

        r = sistema.consultar_reporte("ventas", {"desde": DIA_1, "hasta": DIA_1})
        efectivo = fila(r["filas"], local_codigo="L01", medio_codigo="EFECTIVO")
        tarjeta = fila(r["filas"], local_codigo="L01", medio_codigo="TARJETA")
        assert (efectivo["cobrado"], efectivo["reintegrado"], efectivo["neto"]) == (
            Decimal("180000.00"), Decimal("10000.00"), Decimal("170000.00"))
        assert tarjeta["neto"] == Decimal("160000.00")
        assert r["grafico"] == [{"local_codigo": "L01", "local_nombre": "Local Centro", "neto": Decimal("330000.00")}]
        assert r["totales"]["cantidad_ventas"] == 2

    def test_cada_flujo_usa_su_propia_fecha(self, sistema, reloj):
        bulto(sistema, "L01", "PX", 10)
        linea = vender(sistema, "V-1", "EFECTIVO", 5)
        reloj.ir_al_dia(DIA_1 + timedelta(days=10))
        devolver(sistema, "D-1", "V-1", linea, 2)

        dia_venta = sistema.consultar_reporte("ventas", {"desde": DIA_1, "hasta": DIA_1})
        assert dia_venta["filas"][0]["reintegrado"] == Decimal("0.00")

        despues = sistema.consultar_reporte("ventas", {"desde": DIA_1 + timedelta(days=5),
                                                       "hasta": DIA_1 + timedelta(days=15)})
        assert len(despues["filas"]) == 1  # sólo hay devoluciones y aun así aparece la combinación
        assert (despues["filas"][0]["cantidad_ventas"], despues["filas"][0]["neto"]) == (0, Decimal("-2000.00"))

    def test_varias_devoluciones_no_duplican_lo_cobrado(self, sistema):
        bulto(sistema, "L01", "PX", 10)
        linea = vender(sistema, "V-1", "EFECTIVO", 6)
        for n in range(3):
            devolver(sistema, f"D-{n}", "V-1", linea, 1)
        r = sistema.consultar_reporte("ventas", {"desde": DIA_1, "hasta": DIA_1})
        assert (r["filas"][0]["cobrado"], r["filas"][0]["reintegrado"]) == (Decimal("6000.00"), Decimal("3000.00"))

    def test_filtros_de_local_y_medio(self, sistema):
        bulto(sistema, "L01", "PX", 10)
        bulto(sistema, "L02", "PX", 10)
        vender(sistema, "V-1", "EFECTIVO", 1)
        vender(sistema, "V-2", "TARJETA", 1, local="L02")
        r = sistema.consultar_reporte("ventas", {"desde": DIA_1, "hasta": DIA_1, "medio": "TARJETA"})
        assert [f["local_codigo"] for f in r["filas"]] == ["L02"]

    def test_sin_movimientos(self, sistema):
        r = sistema.consultar_reporte("ventas", {"desde": DIA_1, "hasta": DIA_1})
        assert r["filas"] == [] and r["grafico"] == []

    def test_periodo_invertido(self, sistema):  # Reportes.md: período invertido → 422
        with pytest.raises(ValueError, match="invertido"):
            sistema.consultar_reporte("ventas", {"desde": DIA_1, "hasta": DIA_1 - timedelta(days=1)})

    def test_periodo_obligatorio(self, sistema):
        with pytest.raises(ValueError, match="obligatorio"):
            sistema.consultar_reporte("ventas", {})

    def test_reporte_inexistente(self, sistema):
        with pytest.raises(NoEncontrado):
            sistema.consultar_reporte("clientes", {})


# ---------------------------------------------------------------------------
# R2 Productos vendidos y margen
# ---------------------------------------------------------------------------


class TestR2Productos:
    def test_ejemplo_del_documento(self, sistema):
        bulto(sistema, "L01", "PX", 10)
        linea = vender(sistema, "V-1", "EFECTIVO", 10)
        devolver(sistema, "D-1", "V-1", linea, 2, apta=False)

        r = sistema.consultar_reporte("productos", {"desde": DIA_1, "hasta": DIA_1})
        px = fila(r["filas"], producto_codigo="PX")
        assert px["unidades_netas"] == 8
        assert (px["importe_neto"], px["costo_neto"], px["margen"]) == (
            Decimal("8000.00"), Decimal("4800.00"), Decimal("3200.00"))
        assert (px["devueltas_aptas"], px["devueltas_no_aptas"]) == (0, 2)

    def test_ranking(self, sistema):
        bulto(sistema, "L01", "PX", 10)
        bulto(sistema, "L01", "P002", 10)
        bulto(sistema, "L01", "P003", 10)
        vender(sistema, "V-1", "EFECTIVO", 3)  # PX: 3 unidades
        vender(sistema, "V-2", "EFECTIVO", 5, producto="P002")  # 5 unidades
        vender(sistema, "V-3", "EFECTIVO", 3, producto="P003")  # 3 unidades, margen 1230 > 1200 de PX
        r = sistema.consultar_reporte("productos", {"desde": DIA_1, "hasta": DIA_1})
        assert [(f["posicion"], f["producto_codigo"]) for f in r["filas"]] == [(1, "P002"), (2, "P003"), (3, "PX")]

    def test_usa_costos_historicos(self, sistema):
        bulto(sistema, "L01", "PX", 10)
        vender(sistema, "V-1", "EFECTIVO", 1)
        sistema.registrar_ingreso({"numero": "ING-2", "producto_codigo": "PX", "proveedor_codigo": "PRV01",
                                   "cantidad": 1, "costo_unitario": "900"})  # cambia el costo vigente
        r = sistema.consultar_reporte("productos", {"desde": DIA_1, "hasta": DIA_1})
        assert fila(r["filas"], producto_codigo="PX")["margen"] == Decimal("400.00")


# ---------------------------------------------------------------------------
# R3 Existencias y mínimos
# ---------------------------------------------------------------------------


class TestR3Existencias:
    def test_ejemplo_del_documento(self, sistema):
        bulto(sistema, "L01", "PX", 4)
        sistema.configurar_minimo("L01", "PX", 10)
        bulto(sistema, "L01", "PX", 8, hasta="EN_TRANSITO")

        r = sistema.consultar_reporte("existencias", {"sucursal": "L01", "producto": "PX"})
        px = r["filas"][0]
        assert (px["disponible"], px["minimo"], px["faltante"], px["en_transito"]) == (4, 10, 6, 8)
        assert px["bajo_minimo"]

    def test_circuito_logistico_por_estado(self, sistema):
        bulto(sistema, "L02", "PX", 3, hasta="PREPARADO")
        bulto(sistema, "L02", "PX", 2, hasta="PRECINTADO")
        bulto(sistema, "L02", "PX", 5, hasta="RECIBIDO")
        bulto(sistema, "L02", "PX", 7, hasta="RECHAZADO_PRECINTO", motivo="Roto")
        bulto(sistema, "L02", "PX", 1)  # verificado: ya es disponible, no aparece en el circuito

        r = sistema.consultar_reporte("existencias", {"producto": "PX"})
        cd = fila(r["filas"], sucursal_codigo="CD")
        l02 = fila(r["filas"], sucursal_codigo="L02")
        assert cd["comprometido_salida"] == 5
        assert cd["disponible"] == 2000 - 18
        assert (l02["disponible"], l02["pendiente_despacho"], l02["recibido_sin_verificar"], l02["rechazado"]) == (
            1, 5, 5, 7)

    def test_devolucion_no_apta_fuera_de_venta(self, sistema):
        bulto(sistema, "L01", "PX", 5)
        linea = vender(sistema, "V-1", "EFECTIVO", 3)
        devolver(sistema, "D-1", "V-1", linea, 2, apta=False)
        r = sistema.consultar_reporte("existencias", {"sucursal": "L01", "producto": "PX"})
        assert (r["filas"][0]["disponible"], r["filas"][0]["devuelto_no_apto"]) == (2, 2)

    def test_solo_bajo_minimo(self, sistema):
        r = sistema.consultar_reporte("existencias", {"solo_bajo_minimo": True})
        assert r["filas"] and all(f["bajo_minimo"] for f in r["filas"])
        assert all(f["sucursal_codigo"] != "CD" for f in r["filas"])  # el CD está abastecido


# ---------------------------------------------------------------------------
# R4 Rechazos
# ---------------------------------------------------------------------------


class TestR4Rechazos:
    def test_porcentajes_y_motivos(self, sistema):
        for _ in range(3):
            bulto(sistema, "L01", "PX", 1)
        bulto(sistema, "L01", "PX", 4, hasta="RECHAZADO_PRECINTO", motivo="Precinto roto")
        bulto(sistema, "L01", "PX", 6, hasta="RECHAZADO_PRECINTO", motivo="  precinto   ROTO ")
        bulto(sistema, "L03", "PX", 2, hasta="RECHAZADO_CONTROL", motivo="Faltan unidades")
        bulto(sistema, "L03", "PX", 2, hasta="EN_TRANSITO")  # en curso: no entra en el denominador

        r = sistema.consultar_reporte("rechazos", {"desde": DIA_1, "hasta": DIA_1})
        l01 = fila(r["filas"], destino_codigo="L01")
        assert (l01["verificados"], l01["rechazados"], l01["finalizados"]) == (3, 2, 5)
        assert l01["porcentaje_rechazo"] == Decimal("40.00")
        assert l01["unidades_rechazadas"] == 10
        assert fila(r["filas"], destino_codigo="L02")["porcentaje_rechazo"] is None  # sin datos
        assert fila(r["filas"], destino_codigo="L03")["porcentaje_rechazo"] == Decimal("100.00")
        # Global con totales de bultos (3 de 6), no promedio de porcentajes.
        assert r["totales"]["porcentaje_rechazo"] == Decimal("50.00")
        assert [(m["destino_codigo"], m["motivo"], m["bultos"]) for m in r["motivos"]] == [
            ("L01", "Precinto roto", 2), ("L03", "Faltan unidades", 1)]

    def test_solo_bultos_finalizados_en_el_periodo(self, sistema, reloj):
        codigo = bulto(sistema, "L01", "PX", 1, hasta="RECIBIDO")
        reloj.ir_al_dia(DIA_1 + timedelta(days=3))
        sistema.verificar(codigo, True)
        assert sistema.consultar_reporte("rechazos", {"desde": DIA_1, "hasta": DIA_1})["totales"]["finalizados"] == 0
        siguiente = sistema.consultar_reporte("rechazos", {"desde": DIA_1, "hasta": DIA_1 + timedelta(days=3)})
        assert siguiente["totales"]["finalizados"] == 1


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


class TestPDF:
    def test_los_cuatro_reportes(self, sistema):
        bulto(sistema, "L01", "PX", 10)
        bulto(sistema, "L02", "PX", 3, hasta="RECHAZADO_PRECINTO", motivo="Roto")
        vender(sistema, "V-1", "EFECTIVO", 2)
        exportador = ExportadorPDF()
        periodo = {"desde": DIA_1, "hasta": DIA_1}
        for nombre, filtros in [("ventas", periodo), ("productos", periodo), ("existencias", {}),
                                ("rechazos", periodo)]:
            contenido = exportador.exportar_reporte(sistema.consultar_reporte(nombre, dict(filtros)))
            assert contenido.startswith(b"%PDF"), nombre

    def test_r1_incluye_el_grafico(self, sistema):
        bulto(sistema, "L01", "PX", 10)
        vender(sistema, "V-1", "EFECTIVO", 2)
        datos = sistema.consultar_reporte("ventas", {"desde": DIA_1, "hasta": DIA_1})
        assert b"/Subtype /Image" in ExportadorPDF().exportar_reporte(datos)

    def test_reporte_vacio(self, sistema):
        datos = sistema.consultar_reporte("ventas", {"desde": DIA_1, "hasta": DIA_1})
        contenido = ExportadorPDF().exportar_reporte(datos)
        assert contenido.startswith(b"%PDF") and b"/Subtype /Image" not in contenido  # sin barras ficticias

    def test_comprobante(self, sistema):
        bulto(sistema, "L01", "PX", 10)
        vender(sistema, "V-1", "EFECTIVO", 2)
        assert ExportadorPDF().emitir_comprobante(sistema.consultar_venta("V-1")).startswith(b"%PDF")

    def test_grafico_en_memoria(self):
        imagen = ExportadorPDF().crear_grafico([("A", Decimal("10")), ("B", Decimal("-5"))], "Neto")
        assert imagen.tell() == 0 and imagen.read(8) == b"\x89PNG\r\n\x1a\n"

    def test_formato_argentino(self):
        assert formatear_importe(Decimal("1234567.5")) == "$ 1.234.567,50"
        assert formatear_importe(Decimal("-3450")) == "-$ 3.450,00"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


class TestAPI:
    @pytest.fixture
    def cliente(self, tmp_path):
        ruta = tmp_path / "ventas.sqlite3"
        inicializar(ruta, demo=True)
        with TestClient(create_app(ruta, "0.10", "0.10", tmp_path / "tmp")) as cliente:
            yield cliente

    def test_json_y_pdf_con_los_mismos_filtros(self, cliente):
        hoy = datetime.now(ZONA_HORARIA).date().isoformat()
        respuesta = cliente.get("/api/reportes/ventas", params={"desde": hoy, "hasta": hoy})
        assert respuesta.status_code == 200
        assert respuesta.json()["filtros"] == {"desde": hoy, "hasta": hoy}
        pdf = cliente.get("/api/reportes/ventas/pdf", params={"desde": hoy, "hasta": hoy})
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF")

    def test_existencias_sin_periodo(self, cliente):
        r = cliente.get("/api/reportes/existencias", params={"sucursal": "L01"}).json()
        assert r["filas"][0]["minimo"] == 10
        assert r["totales"]["bajo_minimo"] == 10

    def test_rechazos_sin_datos_es_null(self, cliente):
        r = cliente.get("/api/reportes/rechazos", params={"desde": "2026-01-01", "hasta": "2026-01-31"}).json()
        assert r["filas"][0]["porcentaje_rechazo"] is None

    def test_periodo_invertido_422(self, cliente):
        respuesta = cliente.get("/api/reportes/productos", params={"desde": "2026-02-01", "hasta": "2026-01-01"})
        assert respuesta.status_code == 422
        assert respuesta.json()["detalles"][0]["campo"] == "hasta"

    def test_fecha_mal_formada_422(self, cliente):
        respuesta = cliente.get("/api/reportes/ventas", params={"desde": "ayer", "hasta": "hoy"})
        assert respuesta.status_code == 422

    def test_comprobante(self, cliente):
        assert cliente.get("/api/ventas/NO-EXISTE/comprobante").status_code == 404
