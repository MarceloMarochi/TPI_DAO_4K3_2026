"""API HTTP: rutas, formato de importes y traducción de errores, sobre una base con datos de ejemplo."""

import pytest
from fastapi.testclient import TestClient

from app.inicializar import inicializar
from app.main import create_app


@pytest.fixture
def cliente(tmp_path):
    ruta = tmp_path / "ventas.sqlite3"
    inicializar(ruta, demo=True)
    app = create_app(ruta, "0.10", "0.10", tmp_path / "tmp")
    with TestClient(app) as cliente:
        yield cliente


def abastecer(cliente, destino="L01", producto="P001", cantidad=20, sufijo="1"):
    orden = cliente.post("/api/ordenes", json={"numero": f"O-{sufijo}", "necesidades": [
        {"destino_codigo": destino, "producto_codigo": producto, "cantidad": cantidad}]}).json()
    cliente.post("/api/bultos", json={
        "codigo": f"B-{sufijo}", "orden_numero": f"O-{sufijo}", "destino_codigo": destino,
        "remito_numero": f"R-{sufijo}", "lineas": [{"detalle_id": orden["detalles"][0]["id"], "cantidad": cantidad}]})
    cliente.post(f"/api/bultos/B-{sufijo}/precintar", json={"numero": f"PR-{sufijo}"})
    cliente.post(f"/api/bultos/B-{sufijo}/despachar")
    cliente.post(f"/api/bultos/B-{sufijo}/recibir", json={"intacto": True})
    return cliente.post(f"/api/bultos/B-{sufijo}/verificar", json={"conforme": True})


def venta(numero="V-1", medio="EFECTIVO", cantidad=2, **extra):
    return {"numero": numero, "local_codigo": "L01", "medio_codigo": medio,
            "items": [{"producto_codigo": "P001", "cantidad": cantidad}], **extra}


def test_salud(cliente):
    assert cliente.get("/api/salud").json() == {"estado": "ok"}


def test_openapi_documenta_las_rutas(cliente):
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert "/api/bultos/{codigo}/verificar" in rutas
    assert "/api/ventas/cotizacion" in rutas


class TestCatalogos:
    def test_listados(self, cliente):
        assert len(cliente.get("/api/productos").json()) == 10
        assert [s["codigo"] for s in cliente.get("/api/sucursales").json()] == ["CD", "L01", "L02", "L03"]

    def test_importes_como_texto_decimal(self, cliente):
        producto = cliente.get("/api/productos").json()[0]
        assert producto["precio"] == "4200.00"
        assert producto["costo_referencia"] == "2900.00"

    def test_alta_y_edicion(self, cliente):
        nuevo = {"codigo": "PRV09", "nombre": "Nuevo"}
        assert cliente.post("/api/proveedores", json=nuevo).status_code == 201
        respuesta = cliente.put("/api/proveedores/PRV09", json={"nombre": "Renombrado"})
        assert respuesta.json() == {"codigo": "PRV09", "nombre": "Renombrado"}

    def test_duplicado_409(self, cliente):  # RN-01
        respuesta = cliente.post("/api/proveedores", json={"codigo": "PRV01", "nombre": "Repetido"})
        assert respuesta.status_code == 409
        assert respuesta.json()["codigo"] == "CONFLICTO"

    def test_editar_inexistente_404(self, cliente):
        respuesta = cliente.put("/api/proveedores/NADA", json={"nombre": "X"})
        assert respuesta.status_code == 404
        assert respuesta.json()["codigo"] == "NO_ENCONTRADO"

    def test_dato_invalido_422_con_campo(self, cliente):
        respuesta = cliente.post("/api/productos", json={
            "codigo": "P099", "nombre": "X", "categoria": "C", "proveedor_codigo": "PRV01",
            "precio": "-5", "costo_referencia": "1"})
        assert respuesta.status_code == 422
        assert respuesta.json()["detalles"][0]["campo"] == "precio"

    def test_estructura_invalida_422_uniforme(self, cliente):
        respuesta = cliente.post("/api/proveedores", json={"codigo": "X"})
        cuerpo = respuesta.json()
        assert respuesta.status_code == 422
        assert cuerpo["codigo"] == "DATO_INVALIDO"
        assert cuerpo["detalles"][0]["campo"] == "nombre"

    def test_campos_desconocidos_rechazados(self, cliente):
        respuesta = cliente.post("/api/proveedores", json={"codigo": "X", "nombre": "Y", "es_cd": True})
        assert respuesta.status_code == 422

    def test_minimo(self, cliente):
        respuesta = cliente.put("/api/existencias/L01/P001/minimo", json={"minimo": 30})
        assert respuesta.json()["faltante"] == 30

    def test_ingreso(self, cliente):
        respuesta = cliente.post("/api/ingresos", json={
            "numero": "ING-99", "producto_codigo": "P001", "proveedor_codigo": "PRV01",
            "cantidad": 10, "costo_unitario": "3000.50"})
        assert respuesta.status_code == 201
        assert respuesta.json()["importe"] == "30005.00"
        assert cliente.get("/api/existencias", params={"sucursal": "CD", "producto": "P001"}).json()[0][
            "disponible"] == 210


class TestImportacion:
    def test_csv_valido(self, cliente):
        archivo = "codigo,nombre\nPRV10,Desde CSV\nPRV11,Otro\n".encode("utf-8")
        respuesta = cliente.post("/api/importaciones/proveedores",
                                 files={"archivo": ("lo-que-sea.csv", archivo, "text/csv")})
        assert respuesta.json() == {"tipo": "proveedores", "filas_importadas": 2}

    def test_csv_con_errores(self, cliente):
        archivo = "codigo,nombre\nPRV10,Bien\nPRV01,Repetido\n".encode("utf-8")
        respuesta = cliente.post("/api/importaciones/proveedores",
                                 files={"archivo": ("x.csv", archivo, "text/csv")})
        cuerpo = respuesta.json()
        assert respuesta.status_code == 422
        assert cuerpo["codigo"] == "IMPORTACION_INVALIDA"
        assert cuerpo["detalles"][0]["fila"] == 3
        assert "PRV10" not in [p["codigo"] for p in cliente.get("/api/proveedores").json()]

    def test_tipo_desconocido(self, cliente):
        respuesta = cliente.post("/api/importaciones/clientes",
                                 files={"archivo": ("x.csv", b"a,b\n1,2\n", "text/csv")})
        assert respuesta.status_code == 422

    def test_no_quedan_temporales(self, cliente, tmp_path):
        cliente.post("/api/importaciones/proveedores",
                     files={"archivo": ("x.csv", b"codigo,nombre\nPRV12,X\n", "text/csv")})
        assert list((tmp_path / "tmp").iterdir()) == []


class TestLogistica:
    def test_recorrido_completo(self, cliente):
        respuesta = abastecer(cliente)
        bulto = respuesta.json()
        assert respuesta.status_code == 200
        assert bulto["estado"] == "VERIFICADO"
        assert len(bulto["historial"]) == 5
        assert bulto["historial"][0]["fecha"].endswith("-03:00")
        assert cliente.get("/api/bultos", params={"estado": "VERIFICADO"}).json()[0]["codigo"] == "B-1"

    def test_acciones_permitidas(self, cliente):
        orden = cliente.post("/api/ordenes", json={"numero": "O-1", "necesidades": [
            {"destino_codigo": "L01", "producto_codigo": "P001", "cantidad": 5}]}).json()
        bulto = cliente.post("/api/bultos", json={
            "codigo": "B-1", "orden_numero": "O-1", "destino_codigo": "L01", "remito_numero": "R-1",
            "lineas": [{"detalle_id": orden["detalles"][0]["id"], "cantidad": 5}]}).json()
        assert bulto["acciones_permitidas"] == ["precintar"]

    def test_transicion_invalida_409(self, cliente):  # RN-15
        abastecer(cliente)
        respuesta = cliente.post("/api/bultos/B-1/despachar")
        assert respuesta.status_code == 409
        assert "VERIFICADO" in respuesta.json()["mensaje"]

    def test_bulto_inexistente_404(self, cliente):
        assert cliente.get("/api/bultos/NADA").status_code == 404

    def test_precinto_roto_sin_motivo_422(self, cliente):  # RN-16
        orden = cliente.post("/api/ordenes", json={"numero": "O-1", "necesidades": [
            {"destino_codigo": "L01", "producto_codigo": "P001", "cantidad": 5}]}).json()
        cliente.post("/api/bultos", json={
            "codigo": "B-1", "orden_numero": "O-1", "destino_codigo": "L01", "remito_numero": "R-1",
            "lineas": [{"detalle_id": orden["detalles"][0]["id"], "cantidad": 5}]})
        cliente.post("/api/bultos/B-1/precintar", json={"numero": "PR-1"})
        cliente.post("/api/bultos/B-1/despachar")
        respuesta = cliente.post("/api/bultos/B-1/recibir", json={"intacto": False})
        assert respuesta.status_code == 422
        assert cliente.get("/api/bultos/B-1").json()["estado"] == "EN_TRANSITO"

    def test_ordenes_con_pendientes(self, cliente):
        cliente.post("/api/ordenes", json={"numero": "O-1", "necesidades": [
            {"destino_codigo": "L02", "producto_codigo": "P003", "cantidad": 8}]})
        ordenes = cliente.get("/api/ordenes", params={"pendientes": True}).json()
        assert [(o["numero"], o["pendiente"]) for o in ordenes] == [("O-1", 8)]


class TestCaja:
    def test_medios_de_pago(self, cliente):
        assert cliente.get("/api/medios-pago").json() == [
            {"codigo": "EFECTIVO", "tipo": "descuento", "tasa": "0.10"},
            {"codigo": "TARJETA", "tipo": "recargo", "tasa": "0.10"},
        ]

    def test_cotizar_y_confirmar(self, cliente):
        abastecer(cliente)
        cotizacion = cliente.post("/api/ventas/cotizacion", json={
            "local_codigo": "L01", "medio_codigo": "TARJETA",
            "items": [{"producto_codigo": "P001", "cantidad": 2}]}).json()
        assert (cotizacion["subtotal"], cotizacion["ajuste"], cotizacion["total"]) == ("8400.00", "840.00", "9240.00")

        respuesta = cliente.post("/api/ventas", json=venta(medio="TARJETA", total_esperado=cotizacion["total"]))
        assert respuesta.status_code == 201
        assert respuesta.json()["total_cobrado"] == "9240.00"
        assert cliente.get("/api/ventas/V-1").json()["lineas"][0]["cantidad_restante"] == 2

    def test_total_cambiado_409(self, cliente):  # RN-23
        abastecer(cliente)
        respuesta = cliente.post("/api/ventas", json=venta(total_esperado="1.00"))
        assert respuesta.status_code == 409
        assert cliente.get("/api/ventas").json() == []

    def test_sin_stock_409(self, cliente):  # RN-20
        respuesta = cliente.post("/api/ventas", json=venta())
        assert respuesta.status_code == 409
        assert "Stock insuficiente" in respuesta.json()["mensaje"]

    def test_devolucion(self, cliente):
        abastecer(cliente)
        linea = cliente.post("/api/ventas", json=venta(cantidad=3)).json()["lineas"][0]["id"]
        respuesta = cliente.post("/api/devoluciones", json={
            "numero": "D-1", "venta_numero": "V-1", "detalle_id": linea, "cantidad": 1,
            "apta_reventa": True, "motivo": "Cambio de producto"})
        assert respuesta.status_code == 201
        assert respuesta.json()["importe_reintegrado"] == "3780.00"
        assert cliente.get("/api/devoluciones/D-1").json()["numero"] == "D-1"

    def test_devolucion_excedida_409(self, cliente):  # RN-25
        abastecer(cliente)
        linea = cliente.post("/api/ventas", json=venta(cantidad=1)).json()["lineas"][0]["id"]
        respuesta = cliente.post("/api/devoluciones", json={
            "numero": "D-1", "venta_numero": "V-1", "detalle_id": linea, "cantidad": 2,
            "apta_reventa": True, "motivo": "X"})
        assert respuesta.status_code == 409
