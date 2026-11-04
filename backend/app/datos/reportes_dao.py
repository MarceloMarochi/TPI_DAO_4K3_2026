"""ReportesDAO: las cuatro consultas agregadas de los reportes.

Devuelve cantidades y sumas ya agrupadas. Las fórmulas derivadas (neto, margen,
faltante, porcentaje) y los totales los calcula SistemaVentas.

Regla para no duplicar importes: ventas y devoluciones se agregan POR SEPARADO
(cada una con su propia fecha) y recién después se unen por clave.
Los períodos llegan como texto ISO: desde inclusive, hasta exclusive.
"""

from __future__ import annotations

from app.datos.conexion import ConexionSQLite
from app.datos.formatos import desde_centavos


class ReportesDAO:
    def __init__(self, conexion: ConexionSQLite):
        self._conexion = conexion

    # ------------------------------------------------------------------
    # R1 Ventas e ingresos por local y medio de pago
    # ------------------------------------------------------------------

    def ventas(self, filtros: dict) -> list[dict]:
        filas = self._conexion.consultar(
            """
            WITH v AS (
                SELECT local_codigo, medio_codigo,
                       COUNT(*) AS cantidad_ventas,
                       SUM(total_cobrado_centavos) AS cobrado
                FROM ventas
                WHERE fecha >= :desde AND fecha < :hasta
                  AND (:local IS NULL OR local_codigo = :local)
                  AND (:medio IS NULL OR medio_codigo = :medio)
                GROUP BY local_codigo, medio_codigo
            ),
            d AS (
                SELECT ve.local_codigo, ve.medio_codigo,
                       SUM(de.importe_reintegrado_centavos) AS reintegrado
                FROM devoluciones de
                JOIN ventas ve ON ve.numero = de.venta_numero
                WHERE de.fecha >= :desde AND de.fecha < :hasta
                  AND (:local IS NULL OR ve.local_codigo = :local)
                  AND (:medio IS NULL OR ve.medio_codigo = :medio)
                GROUP BY ve.local_codigo, ve.medio_codigo
            ),
            claves AS (
                SELECT local_codigo, medio_codigo FROM v
                UNION
                SELECT local_codigo, medio_codigo FROM d
            )
            SELECT c.local_codigo, s.nombre AS local_nombre, c.medio_codigo,
                   COALESCE(v.cantidad_ventas, 0) AS cantidad_ventas,
                   COALESCE(v.cobrado, 0) AS cobrado,
                   COALESCE(d.reintegrado, 0) AS reintegrado
            FROM claves c
            JOIN sucursales s ON s.codigo = c.local_codigo
            LEFT JOIN v ON v.local_codigo = c.local_codigo AND v.medio_codigo = c.medio_codigo
            LEFT JOIN d ON d.local_codigo = c.local_codigo AND d.medio_codigo = c.medio_codigo
            ORDER BY c.local_codigo, c.medio_codigo
            """,
            filtros,
        )
        return [
            dict(f) | {"cobrado": desde_centavos(f["cobrado"]), "reintegrado": desde_centavos(f["reintegrado"])}
            for f in filas
        ]

    # ------------------------------------------------------------------
    # R2 Productos vendidos y margen estimado
    # ------------------------------------------------------------------

    def productos(self, filtros: dict) -> list[dict]:
        filas = self._conexion.consultar(
            """
            WITH v AS (
                SELECT dv.producto_codigo,
                       SUM(dv.cantidad) AS vendidas,
                       SUM(dv.importe_cobrado_centavos) AS cobrado,
                       SUM(dv.cantidad * dv.costo_unitario_centavos) AS costo_vendido
                FROM detalles_venta dv
                JOIN ventas ve ON ve.numero = dv.venta_numero
                WHERE ve.fecha >= :desde AND ve.fecha < :hasta
                  AND (:local IS NULL OR ve.local_codigo = :local)
                GROUP BY dv.producto_codigo
            ),
            d AS (
                SELECT dv.producto_codigo,
                       SUM(de.cantidad) AS devueltas,
                       SUM(CASE WHEN de.apta_reventa = 1 THEN de.cantidad ELSE 0 END) AS devueltas_aptas,
                       SUM(CASE WHEN de.apta_reventa = 0 THEN de.cantidad ELSE 0 END) AS devueltas_no_aptas,
                       SUM(de.importe_reintegrado_centavos) AS reintegrado,
                       SUM(de.cantidad * dv.costo_unitario_centavos) AS costo_devuelto
                FROM devoluciones de
                JOIN detalles_venta dv ON dv.id = de.detalle_venta_id
                JOIN ventas ve ON ve.numero = de.venta_numero
                WHERE de.fecha >= :desde AND de.fecha < :hasta
                  AND (:local IS NULL OR ve.local_codigo = :local)
                GROUP BY dv.producto_codigo
            ),
            claves AS (SELECT producto_codigo FROM v UNION SELECT producto_codigo FROM d)
            SELECT c.producto_codigo, p.nombre AS producto_nombre, p.categoria,
                   COALESCE(v.vendidas, 0) AS vendidas,
                   COALESCE(d.devueltas, 0) AS devueltas,
                   COALESCE(d.devueltas_aptas, 0) AS devueltas_aptas,
                   COALESCE(d.devueltas_no_aptas, 0) AS devueltas_no_aptas,
                   COALESCE(v.cobrado, 0) AS cobrado,
                   COALESCE(d.reintegrado, 0) AS reintegrado,
                   COALESCE(v.costo_vendido, 0) AS costo_vendido,
                   COALESCE(d.costo_devuelto, 0) AS costo_devuelto
            FROM claves c
            JOIN productos p ON p.codigo = c.producto_codigo
            LEFT JOIN v ON v.producto_codigo = c.producto_codigo
            LEFT JOIN d ON d.producto_codigo = c.producto_codigo
            """,
            filtros,
        )
        importes = ("cobrado", "reintegrado", "costo_vendido", "costo_devuelto")
        return [dict(f) | {k: desde_centavos(f[k]) for k in importes} for f in filas]

    # ------------------------------------------------------------------
    # R3 Existencias, mínimos y mercadería en el circuito logístico
    # ------------------------------------------------------------------

    def existencias(self, filtros: dict) -> list[dict]:
        """Fotografía actual. Las cantidades logísticas salen del estado ACTUAL de cada bulto
        (el historial no se suma): así ninguna unidad se cuenta dos veces."""
        filas = self._conexion.consultar(
            """
            WITH contenido AS (
                SELECT b.estado, b.destino_codigo, o.origen_codigo, dr.producto_codigo, db.cantidad
                FROM bultos b
                JOIN ordenes o ON o.numero = b.orden_numero
                JOIN detalles_bulto db ON db.bulto_codigo = b.codigo
                JOIN detalles_reposicion dr ON dr.id = db.detalle_reposicion_id
                WHERE b.estado <> 'VERIFICADO'
            ),
            movimientos AS (
                -- Salida comprometida desde el CD: preparada o precintada, todavía en el CD.
                SELECT origen_codigo AS sucursal, producto_codigo AS producto,
                       cantidad AS comprometido_salida, 0 AS pendiente_despacho, 0 AS en_transito,
                       0 AS recibido_sin_verificar, 0 AS rechazado, 0 AS devuelto_no_apto
                FROM contenido WHERE estado IN ('PREPARADO', 'PRECINTADO')
                UNION ALL
                -- Las mismas unidades vistas desde el local de destino.
                SELECT destino_codigo, producto_codigo, 0,
                       CASE WHEN estado IN ('PREPARADO', 'PRECINTADO') THEN cantidad ELSE 0 END,
                       CASE WHEN estado = 'EN_TRANSITO' THEN cantidad ELSE 0 END,
                       CASE WHEN estado = 'RECIBIDO' THEN cantidad ELSE 0 END,
                       CASE WHEN estado = 'RECHAZADO' THEN cantidad ELSE 0 END,
                       0
                FROM contenido
                UNION ALL
                -- Devoluciones no aptas: fuera de venta en el local.
                SELECT ve.local_codigo, dv.producto_codigo, 0, 0, 0, 0, 0, de.cantidad
                FROM devoluciones de
                JOIN detalles_venta dv ON dv.id = de.detalle_venta_id
                JOIN ventas ve ON ve.numero = de.venta_numero
                WHERE de.apta_reventa = 0
                UNION ALL
                SELECT sucursal_codigo, producto_codigo, 0, 0, 0, 0, 0, 0 FROM existencias
            ),
            agrupado AS (
                SELECT sucursal, producto,
                       SUM(comprometido_salida) AS comprometido_salida,
                       SUM(pendiente_despacho) AS pendiente_despacho,
                       SUM(en_transito) AS en_transito,
                       SUM(recibido_sin_verificar) AS recibido_sin_verificar,
                       SUM(rechazado) AS rechazado,
                       SUM(devuelto_no_apto) AS devuelto_no_apto
                FROM movimientos
                GROUP BY sucursal, producto
            )
            SELECT a.sucursal AS sucursal_codigo, s.nombre AS sucursal_nombre, s.es_cd,
                   a.producto AS producto_codigo, p.nombre AS producto_nombre,
                   COALESCE(e.cantidad, 0) AS disponible, COALESCE(e.minimo, 0) AS minimo,
                   a.comprometido_salida, a.pendiente_despacho, a.en_transito,
                   a.recibido_sin_verificar, a.rechazado, a.devuelto_no_apto
            FROM agrupado a
            JOIN sucursales s ON s.codigo = a.sucursal
            JOIN productos p ON p.codigo = a.producto
            LEFT JOIN existencias e ON e.sucursal_codigo = a.sucursal AND e.producto_codigo = a.producto
            WHERE (:sucursal IS NULL OR a.sucursal = :sucursal)
              AND (:producto IS NULL OR a.producto = :producto)
            ORDER BY s.es_cd DESC, a.sucursal, a.producto
            """,
            filtros,
        )
        return [dict(f) | {"es_cd": bool(f["es_cd"])} for f in filas]

    # ------------------------------------------------------------------
    # R4 Rechazos de bultos
    # ------------------------------------------------------------------

    _FINALIZADOS = """
        SELECT h.bulto_codigo, h.nuevo, h.motivo, b.destino_codigo,
               (SELECT SUM(cantidad) FROM detalles_bulto WHERE bulto_codigo = h.bulto_codigo) AS unidades
        FROM historial_estados h
        JOIN bultos b ON b.codigo = h.bulto_codigo
        WHERE h.nuevo IN ('VERIFICADO', 'RECHAZADO')
          AND h.fecha >= :desde AND h.fecha < :hasta
    """

    def rechazos(self, filtros: dict) -> list[dict]:
        """Por local: bultos que terminaron (transición final) dentro del período.
        Incluye locales sin bultos finalizados para poder mostrarlos 'sin datos'."""
        filas = self._conexion.consultar(
            f"""
            WITH fin AS ({self._FINALIZADOS})
            SELECT s.codigo AS destino_codigo, s.nombre AS destino_nombre,
                   COALESCE(SUM(f.nuevo = 'VERIFICADO'), 0) AS verificados,
                   COALESCE(SUM(f.nuevo = 'RECHAZADO'), 0) AS rechazados,
                   COALESCE(SUM(CASE WHEN f.nuevo = 'RECHAZADO' THEN f.unidades END), 0) AS unidades_rechazadas
            FROM sucursales s
            LEFT JOIN fin f ON f.destino_codigo = s.codigo
            WHERE s.es_cd = 0 AND (:destino IS NULL OR s.codigo = :destino)
            GROUP BY s.codigo
            ORDER BY s.codigo
            """,
            filtros,
        )
        return [dict(f) for f in filas]

    def rechazos_detalle(self, filtros: dict) -> list[dict]:
        """Cada bulto rechazado del período con su motivo (el agrupamiento por motivo se hace en negocio)."""
        filas = self._conexion.consultar(
            f"""
            WITH fin AS ({self._FINALIZADOS})
            SELECT f.destino_codigo, s.nombre AS destino_nombre, f.bulto_codigo, f.motivo, f.unidades
            FROM fin f
            JOIN sucursales s ON s.codigo = f.destino_codigo
            WHERE f.nuevo = 'RECHAZADO' AND (:destino IS NULL OR f.destino_codigo = :destino)
            ORDER BY f.destino_codigo, f.bulto_codigo
            """,
            filtros,
        )
        return [dict(f) for f in filas]
