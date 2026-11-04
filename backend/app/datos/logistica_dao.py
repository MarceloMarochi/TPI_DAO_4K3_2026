"""LogisticaDAO: órdenes de reposición, bultos e historial de estados.

El historial sólo admite INSERT (los triggers bloquean UPDATE y DELETE).
"""

from __future__ import annotations

from app.datos.conexion import ConexionSQLite
from app.datos.formatos import a_bool, a_entero_bool, fecha_a_texto, texto_a_fecha
from app.negocio.estados import estado_desde_nombre
from app.negocio.modelos import (
    Bulto,
    CambioEstado,
    DetalleBulto,
    DetalleReposicion,
    OrdenReposicion,
    Producto,
    Sucursal,
)


class LogisticaDAO:
    def __init__(self, conexion: ConexionSQLite):
        self._conexion = conexion

    # --- Órdenes de reposición ---

    def guardar_orden(self, orden: OrdenReposicion) -> None:
        """Inserta la orden o actualiza su cierre. Asigna el id a los detalles nuevos."""
        existe = self._conexion.consultar_uno("SELECT 1 FROM ordenes WHERE numero = ?", (orden.numero,))
        if existe is None:
            self._conexion.ejecutar(
                "INSERT INTO ordenes (numero, fecha, origen_codigo, cerrada) VALUES (?, ?, ?, ?)",
                (orden.numero, fecha_a_texto(orden.fecha), orden.origen.codigo, int(orden.cerrada)),
            )
        else:
            self._conexion.ejecutar(
                "UPDATE ordenes SET cerrada = ? WHERE numero = ?", (int(orden.cerrada), orden.numero)
            )
        for detalle in orden.detalles:
            if detalle.id is None:
                cursor = self._conexion.ejecutar(
                    """INSERT INTO detalles_reposicion (orden_numero, destino_codigo, producto_codigo, cantidad)
                       VALUES (?, ?, ?, ?)""",
                    (orden.numero, detalle.destino.codigo, detalle.producto.codigo, detalle.cantidad),
                )
                detalle.asignar_id(cursor.lastrowid)
            elif not orden.cerrada:
                self._conexion.ejecutar(
                    "UPDATE detalles_reposicion SET cantidad = ? WHERE id = ?", (detalle.cantidad, detalle.id)
                )

    def buscar_orden(self, numero: str, productos: dict[str, Producto],
                     sucursales: dict[str, Sucursal]) -> OrdenReposicion | None:
        fila = self._conexion.consultar_uno("SELECT * FROM ordenes WHERE numero = ?", (numero,))
        if fila is None:
            return None
        detalles = [
            DetalleReposicion(sucursales[d["destino_codigo"]], productos[d["producto_codigo"]],
                              d["cantidad"], id=d["id"])
            for d in self._conexion.consultar(
                "SELECT * FROM detalles_reposicion WHERE orden_numero = ? ORDER BY id", (numero,)
            )
        ]
        return OrdenReposicion.restaurar(
            fila["numero"], sucursales[fila["origen_codigo"]], texto_a_fecha(fila["fecha"]),
            detalles, bool(fila["cerrada"]),
        )

    def asignado_a_detalle(self, detalle_id: int) -> int:
        """Unidades de una línea de la orden ya asignadas a bultos."""
        fila = self._conexion.consultar_uno(
            "SELECT COALESCE(SUM(cantidad), 0) AS asignado FROM detalles_bulto WHERE detalle_reposicion_id = ?",
            (detalle_id,),
        )
        return fila["asignado"]

    def pendientes_de_orden(self, numero: str) -> list[dict]:
        """Por cada línea: solicitado, asignado a bultos y pendiente de preparar."""
        filas = self._conexion.consultar(
            """SELECT d.id, d.destino_codigo, d.producto_codigo, p.nombre AS producto_nombre,
                      d.cantidad AS solicitado,
                      COALESCE((SELECT SUM(db.cantidad) FROM detalles_bulto db
                                WHERE db.detalle_reposicion_id = d.id), 0) AS asignado
               FROM detalles_reposicion d
               JOIN productos p ON p.codigo = d.producto_codigo
               WHERE d.orden_numero = ?
               ORDER BY d.destino_codigo, d.producto_codigo""",
            (numero,),
        )
        return [dict(fila) | {"pendiente": fila["solicitado"] - fila["asignado"]} for fila in filas]

    def listar_ordenes(self, solo_con_pendientes: bool = False) -> list[dict]:
        filas = self._conexion.consultar(
            """SELECT o.numero, o.fecha, o.origen_codigo, o.cerrada,
                      COALESCE(SUM(d.cantidad), 0) AS solicitado,
                      COALESCE(SUM((SELECT SUM(db.cantidad) FROM detalles_bulto db
                                    WHERE db.detalle_reposicion_id = d.id)), 0) AS asignado
               FROM ordenes o
               LEFT JOIN detalles_reposicion d ON d.orden_numero = o.numero
               GROUP BY o.numero
               ORDER BY o.fecha DESC, o.numero DESC"""
        )
        resultado = [
            dict(fila) | {"cerrada": bool(fila["cerrada"]), "pendiente": fila["solicitado"] - fila["asignado"]}
            for fila in filas
        ]
        if solo_con_pendientes:
            resultado = [orden for orden in resultado if orden["pendiente"] > 0]
        return resultado

    # --- Bultos ---

    def guardar_bulto(self, bulto: Bulto) -> None:
        """Inserta un bulto nuevo o actualiza su estado, y agrega al historial los cambios nuevos."""
        existe = self._conexion.consultar_uno("SELECT 1 FROM bultos WHERE codigo = ?", (bulto.codigo,))
        if existe is None:
            self._insertar_bulto(bulto)
        else:
            self._conexion.ejecutar(
                """UPDATE bultos SET estado = ?, precinto_numero = ?, precinto_intacto = ?
                   WHERE codigo = ?""",
                (bulto.estado.nombre(), bulto.precinto_numero, a_entero_bool(bulto.precinto_intacto),
                 bulto.codigo),
            )
        ultima = self._conexion.consultar_uno(
            "SELECT COALESCE(MAX(secuencia), 0) AS ultima FROM historial_estados WHERE bulto_codigo = ?",
            (bulto.codigo,),
        )["ultima"]
        for cambio in bulto.historial:
            if cambio.secuencia > ultima:
                self.registrar_transicion(bulto, cambio)

    def _insertar_bulto(self, bulto: Bulto) -> None:
        self._conexion.ejecutar(
            """INSERT INTO bultos (codigo, orden_numero, destino_codigo, remito_numero,
                                   precinto_numero, precinto_intacto, estado)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (bulto.codigo, bulto.orden.numero, bulto.destino.codigo, bulto.remito_numero,
             bulto.precinto_numero, a_entero_bool(bulto.precinto_intacto), bulto.estado.nombre()),
        )
        for detalle in bulto.detalles:
            if detalle.pedido.id is None:
                raise ValueError("Hay que guardar la orden antes que sus bultos")
            self._conexion.ejecutar(
                "INSERT INTO detalles_bulto (bulto_codigo, detalle_reposicion_id, cantidad) VALUES (?, ?, ?)",
                (bulto.codigo, detalle.pedido.id, detalle.cantidad),
            )

    def registrar_transicion(self, bulto: Bulto, cambio: CambioEstado) -> None:
        self._conexion.ejecutar(
            """INSERT INTO historial_estados (bulto_codigo, secuencia, fecha, anterior, nuevo, motivo)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (bulto.codigo, cambio.secuencia, fecha_a_texto(cambio.fecha), cambio.anterior,
             cambio.nuevo, cambio.motivo),
        )

    def buscar_bulto(self, codigo: str, productos: dict[str, Producto],
                     sucursales: dict[str, Sucursal]) -> Bulto | None:
        fila = self._conexion.consultar_uno("SELECT * FROM bultos WHERE codigo = ?", (codigo,))
        if fila is None:
            return None
        orden = self.buscar_orden(fila["orden_numero"], productos, sucursales)
        detalles = [
            DetalleBulto(orden.buscar_detalle(d["detalle_reposicion_id"]), d["cantidad"])
            for d in self._conexion.consultar(
                "SELECT * FROM detalles_bulto WHERE bulto_codigo = ? ORDER BY detalle_reposicion_id", (codigo,)
            )
        ]
        historial = [
            CambioEstado(h["secuencia"], texto_a_fecha(h["fecha"]), h["anterior"], h["nuevo"], h["motivo"])
            for h in self._conexion.consultar(
                "SELECT * FROM historial_estados WHERE bulto_codigo = ? ORDER BY secuencia", (codigo,)
            )
        ]
        return Bulto.restaurar(
            fila["codigo"], orden, sucursales[fila["destino_codigo"]], fila["remito_numero"], detalles,
            estado_desde_nombre(fila["estado"]), historial,
            precinto_numero=fila["precinto_numero"], precinto_intacto=a_bool(fila["precinto_intacto"]),
        )

    def remito_en_uso(self, numero: str) -> bool:
        return self._conexion.consultar_uno("SELECT 1 FROM bultos WHERE remito_numero = ?", (numero,)) is not None

    def precinto_en_uso(self, numero: str) -> bool:
        return self._conexion.consultar_uno("SELECT 1 FROM bultos WHERE precinto_numero = ?", (numero,)) is not None

    def listar_bultos(self, estado: str | None = None, destino_codigo: str | None = None) -> list[dict]:
        filas = self._conexion.consultar(
            """SELECT b.codigo, b.orden_numero, b.destino_codigo, s.nombre AS destino_nombre,
                      b.remito_numero, b.precinto_numero, b.estado,
                      (SELECT SUM(cantidad) FROM detalles_bulto WHERE bulto_codigo = b.codigo) AS unidades,
                      (SELECT fecha FROM historial_estados WHERE bulto_codigo = b.codigo AND secuencia = 1)
                          AS fecha_preparacion,
                      (SELECT MAX(fecha) FROM historial_estados WHERE bulto_codigo = b.codigo)
                          AS fecha_ultimo_cambio
               FROM bultos b
               JOIN sucursales s ON s.codigo = b.destino_codigo
               WHERE (:estado IS NULL OR b.estado = :estado)
                 AND (:destino IS NULL OR b.destino_codigo = :destino)
               ORDER BY fecha_ultimo_cambio DESC, b.codigo""",
            {"estado": estado, "destino": destino_codigo},
        )
        return [dict(fila) for fila in filas]
