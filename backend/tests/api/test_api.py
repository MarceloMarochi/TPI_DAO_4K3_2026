"""API HTTP: rutas, formato de importes y traducción de errores, sobre una base con datos de ejemplo."""

from decimal import Decimal

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
    total = 4200 * cantidad * (Decimal("0.90") if medio == "EFECTIVO" else Decimal("1.10"))
    return {"numero": numero, "local_codigo": "L01", "medio_codigo": medio,
            "items": [{"producto_codigo": "P001", "cantidad": cantidad}],
            "total_esperado": str(total), **extra}


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
        assert respuesta.json()["detalles"][0]["mensaje"] == "es_cd: no es un dato admitido"


class TestMensajesDeValidacionEnCastellano:
    """Los errores de estructura (Pydantic) llegan en castellano y con el nombre del campo."""

    def _mensajes(self, respuesta):
        assert respuesta.status_code == 422
        return [d["mensaje"] for d in respuesta.json()["detalles"]]

    def test_importe_invalido(self, cliente):
        respuesta = cliente.post("/api/productos", json={
            "codigo": "P099", "nombre": "X", "categoria": "C", "proveedor_codigo": "PRV01",
            "precio": "1500,50", "costo_referencia": "1"})
        assert self._mensajes(respuesta) == [
            "precio: debe ser un número; usá punto para los decimales (por ejemplo 1500.50)"]

    def test_campo_obligatorio(self, cliente):
        assert self._mensajes(cliente.post("/api/proveedores", json={"codigo": "X"})) == ["nombre: es obligatorio"]

    def test_cantidad_no_entera_y_no_positiva(self, cliente):
        ingreso = {"numero": "I-1", "producto_codigo": "P001", "proveedor_codigo": "PRV01", "costo_unitario": "1"}
        assert self._mensajes(cliente.post("/api/ingresos", json={**ingreso, "cantidad": 0})) == [
            "cantidad: debe ser mayor que 0"]
        assert self._mensajes(cliente.post("/api/ingresos", json={**ingreso, "cantidad": "5"})) == [
            "cantidad: debe ser un número entero"]

    def test_linea_de_una_lista(self, cliente):
        respuesta = cliente.post("/api/ventas/cotizacion", json={
            "local_codigo": "L01", "medio_codigo": "EFECTIVO",
            "items": [{"producto_codigo": "P001", "cantidad": 1}, {"producto_codigo": "P002", "cantidad": 1.5}]})
        assert self._mensajes(respuesta) == ["cantidad (línea 2): debe ser un número entero"]
        assert respuesta.json()["detalles"][0]["campo"] == "items.1.cantidad"

    def test_fecha_y_valores_permitidos(self, cliente):
        assert self._mensajes(cliente.get("/api/reportes/ventas?desde=hoy&hasta=2026-11-23")) == [
            "desde: debe ser una fecha con formato AAAA-MM-DD"]
        respuesta = cliente.post("/api/importaciones/clientes", files={"archivo": ("a.csv", b"a")})
        assert self._mensajes(respuesta) == [
            "tipo: debe ser uno de estos valores: 'proveedores', 'sucursales', 'productos', 'ingresos' o 'minimos'"]

    def test_validador_propio_no_se_duplica_el_campo(self, cliente):
        respuesta = cliente.post("/api/ventas", json=venta(total_esperado="1.234"))
        assert self._mensajes(respuesta) == [
            "total_esperado: debe ser no negativo y tener como máximo dos decimales"]

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

    def test_listar_ingresos_del_mas_reciente(self, cliente):
        for numero in ("ING-A", "ING-B"):
            cliente.post("/api/ingresos", json={
                "numero": numero, "producto_codigo": "P001", "proveedor_codigo": "PRV01",
                "cantidad": 1, "costo_unitario": "100"})
        numeros = [i["numero"] for i in cliente.get("/api/ingresos").json()]
        assert numeros[:2] == ["ING-B", "ING-A"]
        assert len(cliente.get("/api/ingresos", params={"limite": 1}).json()) == 1


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

    def test_detalle_informa_lo_solicitado_para_ver_envios_parciales(self, cliente):
        orden = cliente.post("/api/ordenes", json={"numero": "O-1", "necesidades": [
            {"destino_codigo": "L01", "producto_codigo": "P001", "cantidad": 10}]}).json()
        bulto = cliente.post("/api/bultos", json={
            "codigo": "B-1", "orden_numero": "O-1", "destino_codigo": "L01", "remito_numero": "R-1",
            "lineas": [{"detalle_id": orden["detalles"][0]["id"], "cantidad": 6}]}).json()
        assert (bulto["detalles"][0]["cantidad"], bulto["detalles"][0]["solicitado"]) == (6, 10)

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


class TestSugerenciaReposicion:
    """La orden nace de los mínimos: sugerido = faltante − lo que ya está en camino al local."""

    def _sugerido(self, cliente, destino="L01", producto="P001"):
        sugerencias = cliente.get("/api/ordenes/sugerencia").json()
        for s in sugerencias:
            if (s["destino_codigo"], s["producto_codigo"]) == (destino, producto):
                return s
        return None

    def test_con_la_demo_sugiere_el_minimo_de_cada_local(self, cliente):
        sugerencias = cliente.get("/api/ordenes/sugerencia").json()
        # 3 locales x 10 productos, todos en 0 con mínimo 10; el CD nunca es destino.
        assert len(sugerencias) == 30
        assert {s["destino_codigo"] for s in sugerencias} == {"L01", "L02", "L03"}
        assert self._sugerido(cliente) == {
            "destino_codigo": "L01", "destino_nombre": "Local Centro",
            "producto_codigo": "P001", "producto_nombre": "Yerba mate 1 kg",
            "disponible": 0, "minimo": 10, "faltante": 10, "en_camino": 0, "sugerido": 10}

    def test_descuenta_lo_pedido_en_ordenes_anteriores(self, cliente):
        cliente.post("/api/ordenes", json={"numero": "O-1", "necesidades": [
            {"destino_codigo": "L01", "producto_codigo": "P001", "cantidad": 4}]})
        sugerencia = self._sugerido(cliente)
        assert (sugerencia["en_camino"], sugerencia["sugerido"]) == (4, 6)
        cliente.post("/api/ordenes", json={"numero": "O-2", "necesidades": [
            {"destino_codigo": "L01", "producto_codigo": "P001", "cantidad": 6}]})
        assert self._sugerido(cliente) is None  # ya está todo pedido: no se pide dos veces

    def test_lo_verificado_ya_no_se_sugiere(self, cliente):
        abastecer(cliente, cantidad=20)  # disponible 20 > mínimo 10
        assert self._sugerido(cliente) is None

    def test_lo_rechazado_se_vuelve_a_sugerir(self, cliente):
        orden = cliente.post("/api/ordenes", json={"numero": "O-1", "necesidades": [
            {"destino_codigo": "L01", "producto_codigo": "P001", "cantidad": 10}]}).json()
        cliente.post("/api/bultos", json={
            "codigo": "B-1", "orden_numero": "O-1", "destino_codigo": "L01", "remito_numero": "R-1",
            "lineas": [{"detalle_id": orden["detalles"][0]["id"], "cantidad": 10}]})
        cliente.post("/api/bultos/B-1/precintar", json={"numero": "PR-1"})
        cliente.post("/api/bultos/B-1/despachar")
        assert self._sugerido(cliente) is None  # en tránsito: está en camino
        cliente.post("/api/bultos/B-1/recibir", json={"intacto": False, "motivo": "Precinto roto"})
        sugerencia = self._sugerido(cliente)
        assert (sugerencia["en_camino"], sugerencia["sugerido"]) == (0, 10)

    def test_no_se_confunde_con_el_numero_de_orden(self, cliente):
        assert cliente.get("/api/ordenes/sugerencia").status_code == 200
        assert cliente.get("/api/ordenes/O-NO-EXISTE").status_code == 404


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


class TestContratoEstricto:
    @pytest.mark.parametrize("cantidad", [True, False, "2", 2.0, 1.5, 0, -1])
    @pytest.mark.parametrize("ruta,cuerpo,campo", [
        ("ingresos", {"numero": "IX", "producto_codigo": "P001", "proveedor_codigo": "PRV01", "costo_unitario": "1"}, "cantidad"),
        ("ordenes", {"numero": "OX", "necesidades": [{"destino_codigo": "L01", "producto_codigo": "P001"}]}, "necesidades.0.cantidad"),
        ("bultos", {"codigo": "BX", "orden_numero": "OX", "destino_codigo": "L01", "remito_numero": "RX", "lineas": [{"detalle_id": 1}]}, "lineas.0.cantidad"),
        ("ventas/cotizacion", {"local_codigo": "L01", "medio_codigo": "EFECTIVO", "items": [{"producto_codigo": "P001"}]}, "items.0.cantidad"),
        ("ventas", {"numero": "VX", "local_codigo": "L01", "medio_codigo": "EFECTIVO", "total_esperado": "1", "items": [{"producto_codigo": "P001"}]}, "items.0.cantidad"),
        ("devoluciones", {"numero": "DX", "venta_numero": "VX", "detalle_id": 1, "apta_reventa": True, "motivo": "Cambio"}, "cantidad"),
    ])
    def test_cantidad_invalida_se_rechaza_antes_del_dominio(self, cliente, cantidad, ruta, cuerpo, campo):
        import copy
        datos = copy.deepcopy(cuerpo)
        destino = datos
        for parte in campo.split(".")[:-1]:
            destino = destino[int(parte)] if parte.isdigit() else destino[parte]
        destino["cantidad"] = cantidad
        respuesta = cliente.post(f"/api/{ruta}", json=datos)
        assert respuesta.status_code == 422
        assert campo in [d["campo"] for d in respuesta.json()["detalles"]]
        assert cliente.get("/api/ventas").json() == []

    @pytest.mark.parametrize("valor", [True, False, "2", 2.0, 1.5, -1])
    def test_minimos_enteros_estrictos(self, cliente, valor):
        respuesta = cliente.put("/api/existencias/L01/P001/minimo", json={"minimo": valor})
        assert respuesta.status_code == 422
        assert respuesta.json()["detalles"][0]["campo"] == "minimo"

    def test_minimo_cero_valido(self, cliente):
        assert cliente.put("/api/existencias/L01/P001/minimo", json={"minimo": 0}).status_code == 200

    @pytest.mark.parametrize("valor", [None, True, "NaN", "Infinity", "1.001", "-1"])
    def test_total_esperado_invalido(self, cliente, valor):
        abastecer(cliente)
        r = cliente.post("/api/ventas", json=venta(total_esperado=valor))
        assert r.status_code == 422
        assert "total_esperado" in [d["campo"] for d in r.json()["detalles"]]
        assert cliente.get("/api/ventas").json() == []
        assert cliente.get("/api/existencias", params={"sucursal": "L01", "producto": "P001"}).json()[0]["disponible"] == 20

    def test_total_esperado_no_puede_omitirse(self, cliente):
        datos = venta()
        datos.pop("total_esperado")
        r = cliente.post("/api/ventas", json=datos)
        assert r.status_code == 422
        assert r.json()["detalles"][0]["campo"] == "total_esperado"


class TestExistenciasDeAltasNuevas:
    def test_producto_nuevo_aparece_en_cero_en_todos_los_establecimientos(self, cliente):
        cliente.post("/api/productos", json={
            "codigo": "P011", "nombre": "Agua", "categoria": "Bebidas", "proveedor_codigo": "PRV01",
            "precio": "900", "costo_referencia": "500"})
        filas = cliente.get("/api/existencias", params={"producto": "P011"}).json()
        assert sorted(f["sucursal_codigo"] for f in filas) == ["CD", "L01", "L02", "L03"]
        assert all(f["disponible"] == 0 and f["minimo"] == 0 for f in filas)

    def test_local_nuevo_aparece_en_cero_para_todos_los_productos(self, cliente):
        cliente.post("/api/sucursales", json={"codigo": "L04", "nombre": "Nuevo", "es_cd": False})
        filas = cliente.get("/api/existencias", params={"sucursal": "L04"}).json()
        assert len(filas) == 10
        assert cliente.put("/api/existencias/L04/P001/minimo", json={"minimo": 5}).json()["faltante"] == 5

    def test_el_alta_no_pisa_existencias_previas(self, cliente):
        cliente.post("/api/sucursales", json={"codigo": "L04", "nombre": "Nuevo", "es_cd": False})
        cd = cliente.get("/api/existencias", params={"sucursal": "CD", "producto": "P001"}).json()[0]
        assert (cd["disponible"], cd["minimo"]) == (200, 40)


class TestBajas:
    def test_proveedor_sin_uso_se_elimina_y_libera_el_codigo(self, cliente):
        cliente.post("/api/proveedores", json={"codigo": "PRV09", "nombre": "Con error"})
        assert cliente.delete("/api/proveedores/PRV09").status_code == 204
        assert cliente.post("/api/proveedores", json={"codigo": "PRV09", "nombre": "Bien"}).status_code == 201

    def test_proveedor_con_productos_no_se_elimina(self, cliente):
        respuesta = cliente.delete("/api/proveedores/PRV01")
        assert respuesta.status_code == 409
        assert "4 productos" in respuesta.json()["mensaje"]

    def test_producto_sin_uso_se_elimina_con_sus_existencias_en_cero(self, cliente):
        cliente.post("/api/productos", json={
            "codigo": "P011", "nombre": "Agua", "categoria": "Bebidas", "proveedor_codigo": "PRV01",
            "precio": "900", "costo_referencia": "500"})
        cliente.put("/api/existencias/L01/P011/minimo", json={"minimo": 5})
        assert cliente.delete("/api/productos/P011").status_code == 204
        assert cliente.get("/api/existencias", params={"producto": "P011"}).json() == []

    def test_producto_con_ingresos_y_stock_no_se_elimina(self, cliente):
        respuesta = cliente.delete("/api/productos/P001")
        assert respuesta.status_code == 409
        assert "1 ingreso," in respuesta.json()["mensaje"]
        assert "200 unidades en stock" in respuesta.json()["mensaje"]

    def test_local_con_bultos_no_se_elimina_y_su_historia_queda(self, cliente):
        abastecer(cliente)
        respuesta = cliente.delete("/api/sucursales/L01")
        assert respuesta.status_code == 409
        assert "1 bulto" in respuesta.json()["mensaje"]
        assert len(cliente.get("/api/bultos/B-1").json()["historial"]) == 5

    def test_local_sin_uso_se_elimina(self, cliente):
        cliente.post("/api/sucursales", json={"codigo": "L04", "nombre": "Por error", "es_cd": False})
        assert cliente.delete("/api/sucursales/L04").status_code == 204
        assert "L04" not in [s["codigo"] for s in cliente.get("/api/sucursales").json()]

    def test_el_cd_no_se_elimina(self, cliente):
        respuesta = cliente.delete("/api/sucursales/CD")
        assert respuesta.status_code == 409
        assert "Centro de Distribución" in respuesta.json()["mensaje"]

    def test_inexistente_404(self, cliente):
        assert cliente.delete("/api/productos/NOPE").status_code == 404
