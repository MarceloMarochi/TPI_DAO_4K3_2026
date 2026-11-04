"""SistemaVentas: único coordinador de los casos de uso.

Se crea una instancia por solicitud, con su propia conexión. Cada operación de
escritura abre una transacción, recarga el catálogo (productos, sucursales y
existencias) DENTRO de ella, aplica las reglas usando los objetos del dominio y
persiste con los DAOs. Si algo falla se revierte todo y los objetos en memoria
se descartan (la próxima operación vuelve a cargar).

No contiene SQL (está en los DAOs) ni fórmulas (están en los modelos).
Recibe y devuelve diccionarios simples para que la API sólo tenga que serializar.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from app import config
from app.datos.carga_csv import leer_csv
from app.datos.catalogo_dao import CatalogoDAO
from app.datos.conexion import ConexionSQLite
from app.datos.formatos import fecha_a_texto
from app.datos.logistica_dao import LogisticaDAO
from app.datos.reportes_dao import ReportesDAO
from app.datos.venta_dao import VentaDAO
from app.negocio.comunes import ZONA_HORARIA, a_decimal, ahora, redondear, validar_texto
from app.negocio.errores import Conflicto, ErrorImportacion, NoEncontrado
from app.negocio.modelos import (
    Bulto,
    Devolucion,
    IngresoStock,
    OrdenReposicion,
    Producto,
    Sucursal,
    Venta,
)
from app.negocio.pagos import Efectivo, MedioPago, Tarjeta

TIPOS_CATALOGO = ("proveedor", "sucursal", "producto")


class SistemaVentas:
    def __init__(self, conexion: ConexionSQLite,
                 descuento_efectivo=config.TASA_DESCUENTO_EFECTIVO,
                 recargo_tarjeta=config.TASA_RECARGO_TARJETA):
        self._conexion = conexion
        self._catalogo = CatalogoDAO(conexion)
        self._logistica = LogisticaDAO(conexion)
        self._ventas = VentaDAO(conexion)
        self._reportes = ReportesDAO(conexion)
        # Las estrategias se crean (y sus tasas se validan) al iniciar.
        self._medios: dict[str, MedioPago] = {
            Efectivo.CODIGO: Efectivo(descuento_efectivo),
            Tarjeta.CODIGO: Tarjeta(recargo_tarjeta),
        }
        self._productos: dict[str, Producto] = {}
        self._sucursales: dict[str, Sucursal] = {}
        self._proveedores: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Infraestructura de la operación
    # ------------------------------------------------------------------

    def _cargar(self) -> None:
        self._productos, self._sucursales = self._catalogo.cargar_catalogo()
        self._proveedores = {p["codigo"]: p for p in self._catalogo.listar_proveedores()}

    @contextmanager
    def _escritura(self):
        """Transacción + catálogo leído dentro de ella (nadie puede cambiar el stock mientras tanto)."""
        with self._conexion.transaccion():
            self._cargar()
            yield

    def _producto(self, codigo) -> Producto:
        producto = self._productos.get(codigo)
        if producto is None:
            raise NoEncontrado(f"No existe el producto {codigo}")
        return producto

    def _sucursal(self, codigo) -> Sucursal:
        sucursal = self._sucursales.get(codigo)
        if sucursal is None:
            raise NoEncontrado(f"No existe el establecimiento {codigo}")
        return sucursal

    def _cd(self) -> Sucursal:
        for sucursal in self._sucursales.values():
            if sucursal.es_cd:
                return sucursal
        raise Conflicto("Todavía no se registró el Centro de Distribución")

    def _medio(self, codigo) -> MedioPago:
        medio = self._medios.get(codigo)
        if medio is None:
            raise ValueError(f"medio_codigo: medio de pago desconocido ({codigo})")
        return medio

    def _validar_proveedor(self, codigo) -> str:
        codigo = validar_texto(codigo, "proveedor_codigo")
        if codigo not in self._proveedores:
            raise ValueError(f"proveedor_codigo: no existe el proveedor {codigo}")
        return codigo

    def _bulto(self, codigo) -> Bulto:
        bulto = self._logistica.buscar_bulto(codigo, self._productos, self._sucursales)
        if bulto is None:
            raise NoEncontrado(f"No existe el bulto {codigo}")
        return bulto

    def _venta(self, numero) -> Venta:
        venta = self._ventas.buscar_venta(numero, self._productos, self._sucursales)
        if venta is None:
            raise NoEncontrado(f"No existe la venta {numero}")
        return venta

    # ------------------------------------------------------------------
    # Catálogos (proceso 1 y 2)
    # ------------------------------------------------------------------

    def guardar_catalogo(self, tipo: str, datos: dict, alta: bool = True) -> dict:
        """Alta (alta=True) o edición de un proveedor, sucursal o producto. Los códigos no cambian."""
        with self._escritura():
            return self._guardar_catalogo(tipo, datos, alta)

    def _guardar_catalogo(self, tipo, datos, alta) -> dict:
        if tipo == "proveedor":
            return self._guardar_proveedor(datos, alta)
        if tipo == "sucursal":
            return self._guardar_sucursal(datos, alta)
        if tipo == "producto":
            return self._guardar_producto(datos, alta)
        raise ValueError(f"tipo: catálogo desconocido ({tipo}); opciones: {', '.join(TIPOS_CATALOGO)}")

    def _verificar_alta_o_edicion(self, existe: bool, alta: bool, descripcion: str) -> None:
        if alta and existe:
            raise Conflicto(f"Ya existe {descripcion}")
        if not alta and not existe:
            raise NoEncontrado(f"No existe {descripcion}")

    def _guardar_proveedor(self, datos, alta) -> dict:
        codigo = validar_texto(datos.get("codigo"), "codigo")
        nombre = validar_texto(datos.get("nombre"), "nombre")
        self._verificar_alta_o_edicion(codigo in self._proveedores, alta, f"el proveedor {codigo}")
        proveedor = {"codigo": codigo, "nombre": nombre}
        self._catalogo.guardar_proveedor(proveedor)
        self._proveedores[codigo] = proveedor
        return dict(proveedor)

    def _guardar_sucursal(self, datos, alta) -> dict:
        codigo = validar_texto(datos.get("codigo"), "codigo")
        existente = self._sucursales.get(codigo)
        self._verificar_alta_o_edicion(existente is not None, alta, f"el establecimiento {codigo}")
        if alta:
            es_cd = _a_bool(datos.get("es_cd", False), "es_cd")
            if es_cd and any(s.es_cd for s in self._sucursales.values()):
                raise Conflicto("Ya existe un Centro de Distribución; sólo puede haber uno")
            sucursal = Sucursal(codigo, datos.get("nombre"), es_cd)
        else:
            sucursal = existente
            if "es_cd" in datos and _a_bool(datos["es_cd"], "es_cd") != sucursal.es_cd:
                raise Conflicto("No se puede cambiar si un establecimiento es el CD")
            sucursal.nombre = datos.get("nombre")
        self._catalogo.guardar_sucursal(sucursal)
        self._sucursales[codigo] = sucursal
        return _sucursal_a_dict(sucursal)

    def _guardar_producto(self, datos, alta) -> dict:
        codigo = validar_texto(datos.get("codigo"), "codigo")
        existente = self._productos.get(codigo)
        self._verificar_alta_o_edicion(existente is not None, alta, f"el producto {codigo}")
        proveedor = self._validar_proveedor(datos.get("proveedor_codigo"))
        if alta:
            producto = Producto(codigo, datos.get("nombre"), datos.get("categoria"), proveedor,
                                datos.get("precio"), datos.get("costo_referencia"))
        else:
            producto = existente
            producto.nombre = datos.get("nombre")
            producto.categoria = datos.get("categoria")
            producto.proveedor_codigo = proveedor
            producto.precio = datos.get("precio")
            if datos.get("costo_referencia") is not None:
                producto.costo_referencia = datos["costo_referencia"]
        self._catalogo.guardar_producto(producto)
        self._productos[codigo] = producto
        return _producto_a_dict(producto)

    def configurar_minimo(self, sucursal_codigo: str, producto_codigo: str, minimo) -> dict:
        with self._escritura():
            return self._configurar_minimo(sucursal_codigo, producto_codigo, minimo)

    def _configurar_minimo(self, sucursal_codigo, producto_codigo, minimo) -> dict:
        sucursal = self._sucursal(sucursal_codigo)
        existencia = sucursal.existencia_para(self._producto(producto_codigo))
        existencia.minimo = _a_entero(minimo, "minimo")
        self._catalogo.guardar_existencias(sucursal)
        return {
            "sucursal_codigo": sucursal.codigo, "producto_codigo": existencia.producto.codigo,
            "disponible": existencia.cantidad, "minimo": existencia.minimo, "faltante": existencia.faltante(),
        }

    # ------------------------------------------------------------------
    # Abastecimiento del CD
    # ------------------------------------------------------------------

    def registrar_ingreso(self, datos: dict) -> dict:
        with self._escritura():
            return self._registrar_ingreso(datos)

    def _registrar_ingreso(self, datos) -> dict:
        numero = validar_texto(datos.get("numero"), "numero")
        if self._catalogo.buscar_ingreso(numero, self._productos) is not None:
            raise Conflicto(f"Ya existe el ingreso {numero}")
        ingreso = IngresoStock(
            numero, self._producto(datos.get("producto_codigo")),
            self._validar_proveedor(datos.get("proveedor_codigo")),
            _a_entero(datos.get("cantidad"), "cantidad"), datos.get("costo_unitario"),
        )
        cd = self._cd()
        ingreso.aplicar(cd)
        self._catalogo.insertar_ingreso(ingreso)
        self._catalogo.guardar_producto(ingreso.producto)  # costo de referencia actualizado
        self._catalogo.guardar_existencias(cd)
        return _ingreso_a_dict(ingreso)

    # ------------------------------------------------------------------
    # Reposición y bultos (procesos 3 a 6)
    # ------------------------------------------------------------------

    def crear_orden(self, datos: dict) -> dict:
        """datos: {numero, necesidades: [{destino_codigo, producto_codigo, cantidad}]}"""
        with self._escritura():
            numero = validar_texto(datos.get("numero"), "numero")
            if self._logistica.buscar_orden(numero, self._productos, self._sucursales) is not None:
                raise Conflicto(f"Ya existe la orden {numero}")
            orden = OrdenReposicion(numero, self._cd())
            for necesidad in datos.get("necesidades") or []:
                orden.agregar_necesidad(
                    self._sucursal(necesidad.get("destino_codigo")),
                    self._producto(necesidad.get("producto_codigo")),
                    _a_entero(necesidad.get("cantidad"), "cantidad"),
                )
            orden.validar()
            self._logistica.guardar_orden(orden)
            return self._orden_a_dict(orden)

    def preparar_bulto(self, datos: dict) -> dict:
        """datos: {codigo, orden_numero, destino_codigo, remito_numero, lineas: [{detalle_id, cantidad}]}

        Descuenta el disponible del CD una única vez y cierra la orden.
        """
        with self._escritura():
            codigo = validar_texto(datos.get("codigo"), "codigo")
            remito = validar_texto(datos.get("remito_numero"), "remito_numero")
            if self._logistica.buscar_bulto(codigo, self._productos, self._sucursales) is not None:
                raise Conflicto(f"Ya existe el bulto {codigo}")
            if self._logistica.remito_en_uso(remito):
                raise Conflicto(f"El remito {remito} ya está asignado a otro bulto")
            orden = self._logistica.buscar_orden(datos.get("orden_numero"), self._productos, self._sucursales)
            if orden is None:
                raise NoEncontrado(f"No existe la orden {datos.get('orden_numero')}")
            destino = self._sucursal(datos.get("destino_codigo"))

            contenido = []
            for linea in datos.get("lineas") or []:
                pedido = orden.buscar_detalle(linea.get("detalle_id"))
                if pedido is None:
                    raise ValueError(f"detalle_id: la línea {linea.get('detalle_id')} no pertenece a la orden")
                cantidad = _a_entero(linea.get("cantidad"), "cantidad")
                pendiente = pedido.pendiente(self._logistica.asignado_a_detalle(pedido.id))
                if cantidad > pendiente:
                    raise Conflicto(
                        f"De {pedido.producto.codigo} para {pedido.destino.codigo} quedan {pendiente} "
                        f"unidades pendientes de preparar; se pidieron {cantidad}"
                    )
                contenido.append((pedido, cantidad))

            bulto = Bulto(codigo, orden, destino, remito, contenido)
            self._logistica.guardar_orden(orden)  # queda cerrada
            self._logistica.guardar_bulto(bulto)
            self._catalogo.guardar_existencias(orden.origen)
            return _bulto_a_dict(bulto)

    def precintar(self, codigo: str, numero: str) -> dict:
        with self._escritura():
            numero = validar_texto(numero, "numero de precinto")
            if self._logistica.precinto_en_uso(numero):
                raise Conflicto(f"El precinto {numero} ya está asignado a otro bulto")
            return self._operar_bulto(codigo, lambda bulto: bulto.precintar(numero))

    def despachar(self, codigo: str) -> dict:
        with self._escritura():
            return self._operar_bulto(codigo, lambda bulto: bulto.despachar())

    def recibir(self, codigo: str, intacto: bool, motivo: str = "") -> dict:
        with self._escritura():
            return self._operar_bulto(codigo, lambda bulto: bulto.recibir(intacto, motivo or ""))

    def verificar(self, codigo: str, conforme: bool, motivo: str = "") -> dict:
        with self._escritura():
            return self._operar_bulto(codigo, lambda bulto: bulto.verificar(conforme, motivo or ""))

    def _operar_bulto(self, codigo, operacion) -> dict:
        """El bulto decide (State); acá sólo se guarda el resultado y el stock del destino."""
        bulto = self._bulto(codigo)
        operacion(bulto)
        self._logistica.guardar_bulto(bulto)
        self._catalogo.guardar_existencias(bulto.destino)
        return _bulto_a_dict(bulto)

    # ------------------------------------------------------------------
    # Ventas y devoluciones (proceso 7)
    # ------------------------------------------------------------------

    def _armar_venta(self, numero, datos) -> Venta:
        venta = Venta(numero, self._sucursal(datos.get("local_codigo")), self._medio(datos.get("medio_codigo")))
        items = datos.get("items") or []
        if not items:
            raise ValueError("items: la venta debe tener al menos un producto")
        for item in items:
            venta.agregar_detalle(self._producto(item.get("producto_codigo")),
                                  _a_entero(item.get("cantidad"), "cantidad"))
        return venta

    def cotizar_venta(self, datos: dict) -> dict:
        """Calcula subtotal, ajuste y total. No guarda ni reserva stock.

        datos: {local_codigo, medio_codigo, items: [{producto_codigo, cantidad}]}
        """
        self._cargar()
        venta = self._armar_venta("COTIZACION", datos)
        return {
            "local_codigo": venta.local.codigo,
            "medio_codigo": venta.medio_codigo,
            "tasa": venta.tasa_aplicada,
            "lineas": [
                {"producto_codigo": d.producto.codigo, "producto_nombre": d.producto.nombre,
                 "cantidad": d.cantidad, "precio_unitario": d.precio_unitario, "subtotal": d.subtotal()}
                for d in venta.detalles
            ],
            "subtotal": venta.subtotal(),
            "ajuste": venta.ajuste(),
            "total": venta.calcular_total(),
        }

    def confirmar_venta(self, datos: dict) -> dict:
        """Igual que cotizar más {numero, total_esperado}. Recalcula todo en el servidor.

        Si el total difiere del que vio el usuario (cambió un precio), no guarda y pide cotizar de nuevo.
        """
        with self._escritura():
            numero = validar_texto(datos.get("numero"), "numero")
            if self._ventas.buscar_venta(numero, self._productos, self._sucursales) is not None:
                raise Conflicto(f"Ya existe la venta {numero}")
            venta = self._armar_venta(numero, datos)
            esperado = datos.get("total_esperado")
            if esperado is not None and redondear(a_decimal(esperado, "total_esperado")) != venta.calcular_total():
                raise Conflicto(
                    f"El total cambió: se esperaba {esperado} y ahora es {venta.calcular_total()}. "
                    "Vuelva a cotizar."
                )
            venta.confirmar()
            self._ventas.insertar_venta(venta)
            self._catalogo.guardar_existencias(venta.local)
            return self._venta_a_dict(venta)

    def devolver(self, datos: dict) -> dict:
        """datos: {numero, venta_numero, detalle_id, cantidad, apta_reventa, motivo}"""
        with self._escritura():
            numero = validar_texto(datos.get("numero"), "numero")
            if self._ventas.buscar_devolucion(numero, self._productos, self._sucursales) is not None:
                raise Conflicto(f"Ya existe la devolución {numero}")
            venta = self._venta(datos.get("venta_numero"))
            detalle = venta.buscar_detalle(datos.get("detalle_id"))
            if detalle is None:
                raise ValueError(f"detalle_id: la línea {datos.get('detalle_id')} no pertenece a la venta")
            ya_devuelto, importe_ya_devuelto = self._ventas.acumulado_devuelto(detalle.id)
            devolucion = Devolucion(numero, venta, detalle, _a_entero(datos.get("cantidad"), "cantidad"),
                                    _a_bool(datos.get("apta_reventa"), "apta_reventa"), datos.get("motivo"))
            devolucion.confirmar(ya_devuelto, importe_ya_devuelto)
            self._ventas.insertar_devolucion(devolucion)
            self._catalogo.guardar_existencias(venta.local)
            return _devolucion_a_dict(devolucion)

    # ------------------------------------------------------------------
    # Importación CSV
    # ------------------------------------------------------------------

    def importar_csv(self, tipo: str, ruta: str | Path) -> dict:
        """Valida todas las filas; si alguna falla no se importa ninguna (una sola transacción).

        tipo: proveedores | sucursales | productos | ingresos | minimos
        El stock inicial se carga como ingresos al CD; nunca directo en un local.
        """
        filas = leer_csv(ruta, tipo)
        with self._escritura():
            errores = []
            for numero_fila, fila in filas:
                try:
                    self._importar_fila(tipo, fila)
                except ValueError as error:  # incluye NoEncontrado y Conflicto
                    errores.append(_error_de_fila(numero_fila, error))
            if errores:
                raise ErrorImportacion(errores)  # provoca el ROLLBACK
        return {"tipo": tipo, "filas_importadas": len(filas)}

    def _importar_fila(self, tipo, fila) -> None:
        if tipo == "proveedores":
            self._guardar_proveedor(fila, alta=True)
        elif tipo == "sucursales":
            self._guardar_sucursal(fila, alta=True)
        elif tipo == "productos":
            self._guardar_producto(fila, alta=True)
        elif tipo == "ingresos":
            self._registrar_ingreso(fila)
        elif tipo == "minimos":
            self._configurar_minimo(fila.get("sucursal_codigo"), fila.get("producto_codigo"), fila.get("minimo"))

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def consultar_catalogo(self, tipo: str | None = None) -> dict | list:
        catalogos = self._catalogo.listar_catalogos()
        if tipo is None:
            return catalogos
        clave = {"proveedor": "proveedores", "sucursal": "sucursales", "producto": "productos"}.get(tipo)
        if clave is None:
            raise ValueError(f"tipo: catálogo desconocido ({tipo})")
        return catalogos[clave]

    def consultar_existencias(self, sucursal_codigo: str | None = None,
                              producto_codigo: str | None = None) -> list[dict]:
        return self._catalogo.consultar_existencias(sucursal_codigo, producto_codigo)

    def consultar_ingreso(self, numero: str) -> dict:
        self._cargar()
        ingreso = self._catalogo.buscar_ingreso(numero, self._productos)
        if ingreso is None:
            raise NoEncontrado(f"No existe el ingreso {numero}")
        return _ingreso_a_dict(ingreso)

    def consultar_orden(self, numero: str) -> dict:
        self._cargar()
        orden = self._logistica.buscar_orden(numero, self._productos, self._sucursales)
        if orden is None:
            raise NoEncontrado(f"No existe la orden {numero}")
        return self._orden_a_dict(orden)

    def listar_ordenes(self, solo_con_pendientes: bool = False) -> list[dict]:
        return self._logistica.listar_ordenes(solo_con_pendientes)

    def consultar_bulto(self, codigo: str) -> dict:
        self._cargar()
        return _bulto_a_dict(self._bulto(codigo))

    def listar_bultos(self, estado: str | None = None, destino_codigo: str | None = None) -> list[dict]:
        return self._logistica.listar_bultos(estado, destino_codigo)

    def consultar_venta(self, numero: str) -> dict:
        self._cargar()
        return self._venta_a_dict(self._venta(numero))

    def listar_ventas(self, local_codigo: str | None = None) -> list[dict]:
        return self._ventas.listar_ventas(local_codigo)

    def consultar_devolucion(self, numero: str) -> dict:
        self._cargar()
        devolucion = self._ventas.buscar_devolucion(numero, self._productos, self._sucursales)
        if devolucion is None:
            raise NoEncontrado(f"No existe la devolución {numero}")
        return _devolucion_a_dict(devolucion)

    def consultar_medios_pago(self) -> list[dict]:
        return [
            {"codigo": Efectivo.CODIGO, "tipo": "descuento", "tasa": self._medios[Efectivo.CODIGO].tasa},
            {"codigo": Tarjeta.CODIGO, "tipo": "recargo", "tasa": self._medios[Tarjeta.CODIGO].tasa},
        ]

    # ------------------------------------------------------------------
    # Reportes R1 a R4
    # ------------------------------------------------------------------

    REPORTES = {
        "ventas": "Ventas e ingresos por local y medio de pago",
        "productos": "Productos vendidos y margen estimado",
        "existencias": "Existencias, mínimos y mercadería en circuito",
        "rechazos": "Rechazos de bultos",
    }

    def consultar_reporte(self, nombre: str, filtros: dict) -> dict:
        """Devuelve {reporte, titulo, generado, filtros, filas, totales, ...} con los indicadores ya calculados.

        Los mismos datos alimentan la respuesta JSON y el PDF.
        """
        calcular = {
            "ventas": self._reporte_ventas,
            "productos": self._reporte_productos,
            "existencias": self._reporte_existencias,
            "rechazos": self._reporte_rechazos,
        }.get(nombre)
        if calcular is None:
            raise NoEncontrado(f"No existe el reporte {nombre}")
        filtros = {clave: valor for clave, valor in filtros.items() if valor not in (None, "")}
        resultado = calcular(filtros)
        return {"reporte": nombre, "titulo": self.REPORTES[nombre], "generado": ahora(),
                "filtros": filtros} | resultado

    def _reporte_ventas(self, filtros) -> dict:
        filas = self._reportes.ventas(
            _periodo(filtros) | {"local": filtros.get("local"), "medio": filtros.get("medio")}
        )
        por_local: dict[str, dict] = {}
        for fila in filas:
            fila["neto"] = fila["cobrado"] - fila["reintegrado"]  # puede ser negativo
            barra = por_local.setdefault(fila["local_codigo"], {
                "local_codigo": fila["local_codigo"], "local_nombre": fila["local_nombre"], "neto": Decimal("0.00")})
            barra["neto"] += fila["neto"]
        return {
            "filas": filas,
            "totales": {
                "cantidad_ventas": sum(f["cantidad_ventas"] for f in filas),
                **{k: _suma(filas, k) for k in ("cobrado", "reintegrado", "neto")},
            },
            "grafico": list(por_local.values()),
        }

    def _reporte_productos(self, filtros) -> dict:
        filas = self._reportes.productos(_periodo(filtros) | {"local": filtros.get("local")})
        for fila in filas:
            fila["unidades_netas"] = fila["vendidas"] - fila["devueltas"]
            fila["importe_neto"] = fila["cobrado"] - fila["reintegrado"]
            fila["costo_neto"] = fila["costo_vendido"] - fila["costo_devuelto"]
            fila["margen"] = fila["importe_neto"] - fila["costo_neto"]
        filas.sort(key=lambda f: (-f["unidades_netas"], -f["margen"], f["producto_codigo"]))
        for posicion, fila in enumerate(filas, start=1):
            fila["posicion"] = posicion
        claves = ("vendidas", "devueltas", "devueltas_aptas", "devueltas_no_aptas", "unidades_netas")
        return {
            "filas": filas,
            "totales": {k: sum(f[k] for f in filas) for k in claves}
                       | {k: _suma(filas, k) for k in ("importe_neto", "costo_neto", "margen")},
        }

    def _reporte_existencias(self, filtros) -> dict:
        filas = self._reportes.existencias(
            {"sucursal": filtros.get("sucursal"), "producto": filtros.get("producto")}
        )
        for fila in filas:
            fila["faltante"] = max(0, fila["minimo"] - fila["disponible"])
            fila["bajo_minimo"] = fila["disponible"] < fila["minimo"]
        if _a_bool(filtros.get("solo_bajo_minimo", False), "solo_bajo_minimo"):
            filas = [f for f in filas if f["bajo_minimo"]]
        return {
            "filas": filas,
            "totales": {
                "filas": len(filas),
                "bajo_minimo": sum(1 for f in filas if f["bajo_minimo"]),
                "faltante": sum(f["faltante"] for f in filas),
                "en_transito": sum(f["en_transito"] for f in filas),
                "recibido_sin_verificar": sum(f["recibido_sin_verificar"] for f in filas),
            },
        }

    def _reporte_rechazos(self, filtros) -> dict:
        consulta = _periodo(filtros) | {"destino": filtros.get("destino")}
        filas = self._reportes.rechazos(consulta)
        for fila in filas:
            fila["finalizados"] = fila["verificados"] + fila["rechazados"]
            fila["porcentaje_rechazo"] = _porcentaje(fila["rechazados"], fila["finalizados"])

        motivos: dict[tuple, dict] = {}
        for rechazo in self._reportes.rechazos_detalle(consulta):
            texto = " ".join((rechazo["motivo"] or "Sin motivo").split()).lower()
            grupo = motivos.setdefault((rechazo["destino_codigo"], texto), {
                "destino_codigo": rechazo["destino_codigo"], "destino_nombre": rechazo["destino_nombre"],
                "motivo": texto[:1].upper() + texto[1:], "bultos": 0, "unidades": 0})
            grupo["bultos"] += 1
            grupo["unidades"] += rechazo["unidades"]

        verificados = sum(f["verificados"] for f in filas)
        rechazados = sum(f["rechazados"] for f in filas)
        return {
            "filas": filas,
            "totales": {
                "verificados": verificados, "rechazados": rechazados, "finalizados": verificados + rechazados,
                # Global con los totales de bultos, no promediando porcentajes de locales.
                "porcentaje_rechazo": _porcentaje(rechazados, verificados + rechazados),
                "unidades_rechazadas": sum(f["unidades_rechazadas"] for f in filas),
            },
            "motivos": sorted(motivos.values(), key=lambda m: (m["destino_codigo"], -m["bultos"], m["motivo"])),
        }

    # --- Representaciones que necesitan consultar a los DAOs ---

    def _orden_a_dict(self, orden: OrdenReposicion) -> dict:
        return {
            "numero": orden.numero, "fecha": orden.fecha, "origen_codigo": orden.origen.codigo,
            "cerrada": orden.cerrada, "detalles": self._logistica.pendientes_de_orden(orden.numero),
        }

    def _venta_a_dict(self, venta: Venta) -> dict:
        devuelto = self._ventas.devuelto_por_detalle(venta.numero)
        subtotal = venta.subtotal()
        lineas = []
        for d in venta.detalles:
            cantidad_devuelta, importe_devuelto = devuelto.get(d.id, (0, Decimal("0.00")))
            lineas.append({
                "id": d.id, "producto_codigo": d.producto.codigo, "producto_nombre": d.producto.nombre,
                "cantidad": d.cantidad, "precio_unitario": d.precio_unitario, "subtotal": d.subtotal(),
                "importe_cobrado": d.importe_cobrado, "cantidad_devuelta": cantidad_devuelta,
                "importe_devuelto": importe_devuelto, "cantidad_restante": d.cantidad - cantidad_devuelta,
            })
        return {
            "numero": venta.numero, "fecha": venta.fecha, "local_codigo": venta.local.codigo,
            "local_nombre": venta.local.nombre, "medio_codigo": venta.medio_codigo, "tasa_aplicada": venta.tasa_aplicada,
            "subtotal": subtotal, "ajuste": venta.total_cobrado - subtotal,
            "total_cobrado": venta.total_cobrado, "comprobante_numero": venta.comprobante_numero,
            "lineas": lineas,
        }


# ----------------------------------------------------------------------
# Funciones auxiliares
# ----------------------------------------------------------------------


def _a_fecha(valor, campo: str) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise ValueError(f"{campo}: debe ser una fecha AAAA-MM-DD") from None


def _periodo(filtros: dict) -> dict:
    """Desde y hasta inclusivos, en hora de Buenos Aires. Internamente: [desde 00:00, día siguiente a hasta 00:00)."""
    if filtros.get("desde") is None or filtros.get("hasta") is None:
        raise ValueError("desde: el período (desde y hasta) es obligatorio")
    desde = _a_fecha(filtros["desde"], "desde")
    hasta = _a_fecha(filtros["hasta"], "hasta")
    if desde > hasta:
        raise ValueError("hasta: el período está invertido (desde es posterior a hasta)")
    filtros["desde"], filtros["hasta"] = desde, hasta
    inicio = datetime.combine(desde, time.min, tzinfo=ZONA_HORARIA)
    fin = datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=ZONA_HORARIA)
    return {"desde": fecha_a_texto(inicio), "hasta": fecha_a_texto(fin)}


def _suma(filas: list[dict], clave: str) -> Decimal:
    return sum((fila[clave] for fila in filas), Decimal("0.00"))


def _porcentaje(parte: int, total: int) -> Decimal | None:
    """None cuando no hay base: el reporte lo muestra como 'sin datos'."""
    if total == 0:
        return None
    return redondear(Decimal(parte) * 100 / Decimal(total))


def _a_entero(valor, campo: str) -> int:
    """Acepta enteros o texto numérico (los CSV llegan como texto)."""
    if isinstance(valor, str):
        try:
            valor = int(valor.strip())
        except ValueError:
            raise ValueError(f"{campo}: debe ser un número entero") from None
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ValueError(f"{campo}: debe ser un número entero")
    return valor


def _a_bool(valor, campo: str) -> bool:
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        texto = valor.strip().lower()
        if texto in ("si", "sí", "s", "true", "verdadero", "1", "x"):
            return True
        if texto in ("no", "n", "false", "falso", "0", ""):
            return False
    raise ValueError(f"{campo}: debe ser sí o no")


def _error_de_fila(numero_fila: int, error: Exception) -> dict:
    mensaje = str(error)
    campo = None
    # Convención de los mensajes de validación: "campo: descripción" (en minúscula).
    if ":" in mensaje and mensaje[:1].islower():
        campo = mensaje.split(":", 1)[0]
    return {"fila": numero_fila, "campo": campo, "mensaje": mensaje}


def _producto_a_dict(p: Producto) -> dict:
    return {
        "codigo": p.codigo, "nombre": p.nombre, "categoria": p.categoria,
        "proveedor_codigo": p.proveedor_codigo, "precio": p.precio, "costo_referencia": p.costo_referencia,
    }


def _sucursal_a_dict(s: Sucursal) -> dict:
    return {"codigo": s.codigo, "nombre": s.nombre, "es_cd": s.es_cd}


def _ingreso_a_dict(i: IngresoStock) -> dict:
    return {
        "numero": i.numero, "fecha": i.fecha, "producto_codigo": i.producto.codigo,
        "proveedor_codigo": i.proveedor_codigo, "cantidad": i.cantidad,
        "costo_unitario": i.costo_unitario, "importe": i.importe(),
    }


def _bulto_a_dict(b: Bulto) -> dict:
    return {
        "codigo": b.codigo, "orden_numero": b.orden.numero, "destino_codigo": b.destino.codigo,
        "remito_numero": b.remito_numero, "precinto_numero": b.precinto_numero,
        "precinto_intacto": b.precinto_intacto, "estado": b.estado.nombre(),
        "estado_remito": b.estado_remito(), "acciones_permitidas": b.acciones_permitidas(),
        "unidades": b.unidades(),
        "detalles": [
            {"detalle_id": d.pedido.id, "producto_codigo": d.producto.codigo,
             "producto_nombre": d.producto.nombre, "cantidad": d.cantidad}
            for d in b.detalles
        ],
        "historial": [
            {"secuencia": c.secuencia, "fecha": c.fecha, "anterior": c.anterior,
             "nuevo": c.nuevo, "motivo": c.motivo}
            for c in b.historial
        ],
    }


def _devolucion_a_dict(d: Devolucion) -> dict:
    return {
        "numero": d.numero, "fecha": d.fecha, "venta_numero": d.venta.numero, "detalle_id": d.detalle.id,
        "producto_codigo": d.detalle.producto.codigo, "cantidad": d.cantidad,
        "apta_reventa": d.apta_reventa, "motivo": d.motivo,
        "importe_reintegrado": d.importe_reintegrado, "medio_codigo": d.medio_codigo,
    }
