"""VentaDAO: ventas, sus detalles y devoluciones.

Sólo inserta y consulta: una venta o devolución confirmada nunca se modifica ni se borra.
"""

from __future__ import annotations

from decimal import Decimal

from app.datos.conexion import ConexionSQLite
from app.datos.formatos import a_centavos, desde_centavos, fecha_a_texto, texto_a_fecha
from app.negocio.modelos import DetalleVenta, Devolucion, Producto, Sucursal, Venta
from app.negocio.pagos import crear_medio_pago


class VentaDAO:
    def __init__(self, conexion: ConexionSQLite):
        self._conexion = conexion

    # --- Ventas ---

    def insertar_venta(self, venta: Venta) -> None:
        if not venta.confirmada:
            raise ValueError("Sólo se guardan ventas confirmadas")
        self._conexion.ejecutar(
            """INSERT INTO ventas (numero, fecha, local_codigo, medio_codigo, tasa_aplicada,
                                   total_cobrado_centavos, comprobante_numero)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (venta.numero, fecha_a_texto(venta.fecha), venta.local.codigo, venta.medio_codigo,
             str(venta.tasa_aplicada), a_centavos(venta.total_cobrado), venta.comprobante_numero),
        )
        for detalle in venta.detalles:
            cursor = self._conexion.ejecutar(
                """INSERT INTO detalles_venta (venta_numero, producto_codigo, cantidad,
                       precio_unitario_centavos, costo_unitario_centavos, importe_cobrado_centavos)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (venta.numero, detalle.producto.codigo, detalle.cantidad,
                 a_centavos(detalle.precio_unitario), a_centavos(detalle.costo_unitario),
                 a_centavos(detalle.importe_cobrado)),
            )
            detalle.asignar_id(cursor.lastrowid)

    def buscar_venta(self, numero: str, productos: dict[str, Producto],
                     sucursales: dict[str, Sucursal]) -> Venta | None:
        fila = self._conexion.consultar_uno("SELECT * FROM ventas WHERE numero = ?", (numero,))
        if fila is None:
            return None
        detalles = [
            DetalleVenta(
                productos[d["producto_codigo"]], d["cantidad"],
                desde_centavos(d["precio_unitario_centavos"]), desde_centavos(d["costo_unitario_centavos"]),
                id=d["id"], importe_cobrado=desde_centavos(d["importe_cobrado_centavos"]),
            )
            for d in self._conexion.consultar(
                "SELECT * FROM detalles_venta WHERE venta_numero = ? ORDER BY id", (numero,)
            )
        ]
        # Strategy reconstruida con la tasa histórica, no con la vigente.
        medio = crear_medio_pago(fila["medio_codigo"], Decimal(fila["tasa_aplicada"]))
        return Venta.restaurar(
            fila["numero"], sucursales[fila["local_codigo"]], medio, texto_a_fecha(fila["fecha"]),
            detalles, desde_centavos(fila["total_cobrado_centavos"]), fila["comprobante_numero"],
        )

    def listar_ventas(self, local_codigo: str | None = None, limite: int = 100) -> list[dict]:
        filas = self._conexion.consultar(
            """SELECT v.numero, v.fecha, v.local_codigo, s.nombre AS local_nombre, v.medio_codigo,
                      v.total_cobrado_centavos, v.comprobante_numero
               FROM ventas v
               JOIN sucursales s ON s.codigo = v.local_codigo
               WHERE (:local IS NULL OR v.local_codigo = :local)
               ORDER BY v.fecha DESC, v.numero DESC
               LIMIT :limite""",
            {"local": local_codigo, "limite": limite},
        )
        return [
            {k: fila[k] for k in fila.keys() if k != "total_cobrado_centavos"}
            | {"total_cobrado": desde_centavos(fila["total_cobrado_centavos"])}
            for fila in filas
        ]

    # --- Devoluciones ---

    def insertar_devolucion(self, devolucion: Devolucion) -> None:
        if not devolucion.confirmada:
            raise ValueError("Sólo se guardan devoluciones confirmadas")
        if devolucion.detalle.id is None:
            raise ValueError("La línea devuelta no pertenece a una venta guardada")
        self._conexion.ejecutar(
            """INSERT INTO devoluciones (numero, fecha, venta_numero, detalle_venta_id, cantidad,
                                         apta_reventa, motivo, importe_reintegrado_centavos)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (devolucion.numero, fecha_a_texto(devolucion.fecha), devolucion.venta.numero,
             devolucion.detalle.id, devolucion.cantidad, int(devolucion.apta_reventa),
             devolucion.motivo, a_centavos(devolucion.importe_reintegrado)),
        )

    def acumulado_devuelto(self, detalle_id: int) -> tuple[int, Decimal]:
        """Cantidad e importe ya devueltos de una línea de venta."""
        fila = self._conexion.consultar_uno(
            """SELECT COALESCE(SUM(cantidad), 0) AS cantidad,
                      COALESCE(SUM(importe_reintegrado_centavos), 0) AS importe
               FROM devoluciones WHERE detalle_venta_id = ?""",
            (detalle_id,),
        )
        return fila["cantidad"], desde_centavos(fila["importe"])

    def devuelto_por_detalle(self, venta_numero: str) -> dict[int, tuple[int, Decimal]]:
        """Por cada línea de la venta: cantidad e importe ya devueltos."""
        filas = self._conexion.consultar(
            """SELECT detalle_venta_id, SUM(cantidad) AS cantidad, SUM(importe_reintegrado_centavos) AS importe
               FROM devoluciones WHERE venta_numero = ? GROUP BY detalle_venta_id""",
            (venta_numero,),
        )
        return {f["detalle_venta_id"]: (f["cantidad"], desde_centavos(f["importe"])) for f in filas}

    def buscar_devolucion(self, numero: str, productos: dict[str, Producto],
                          sucursales: dict[str, Sucursal]) -> Devolucion | None:
        fila = self._conexion.consultar_uno("SELECT * FROM devoluciones WHERE numero = ?", (numero,))
        if fila is None:
            return None
        venta = self.buscar_venta(fila["venta_numero"], productos, sucursales)
        return Devolucion.restaurar(
            fila["numero"], venta, venta.buscar_detalle(fila["detalle_venta_id"]), fila["cantidad"],
            bool(fila["apta_reventa"]), fila["motivo"], texto_a_fecha(fila["fecha"]),
            desde_centavos(fila["importe_reintegrado_centavos"]),
        )
