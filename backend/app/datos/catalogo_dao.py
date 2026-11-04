"""CatalogoDAO: proveedores, productos, sucursales, existencias e ingresos al CD.

Los proveedores son filas simples de código y nombre (no hay clase Proveedor).
"""

from __future__ import annotations

from app.datos.conexion import ConexionSQLite
from app.datos.formatos import a_centavos, desde_centavos, fecha_a_texto, texto_a_fecha
from app.negocio.modelos import IngresoStock, Producto, Sucursal


class CatalogoDAO:
    def __init__(self, conexion: ConexionSQLite):
        self._conexion = conexion

    # --- Proveedores ---

    def guardar_proveedor(self, datos: dict) -> None:
        """Alta o actualización del nombre. El código nunca cambia."""
        self._conexion.ejecutar(
            """INSERT INTO proveedores (codigo, nombre) VALUES (:codigo, :nombre)
               ON CONFLICT (codigo) DO UPDATE SET nombre = excluded.nombre""",
            {"codigo": datos["codigo"], "nombre": datos["nombre"]},
        )

    def listar_proveedores(self) -> list[dict]:
        filas = self._conexion.consultar("SELECT codigo, nombre FROM proveedores ORDER BY codigo")
        return [dict(fila) for fila in filas]

    # --- Productos ---

    def guardar_producto(self, producto: Producto) -> None:
        self._conexion.ejecutar(
            """INSERT INTO productos (codigo, nombre, categoria, proveedor_codigo,
                                      precio_centavos, costo_referencia_centavos)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT (codigo) DO UPDATE SET
                   nombre = excluded.nombre,
                   categoria = excluded.categoria,
                   proveedor_codigo = excluded.proveedor_codigo,
                   precio_centavos = excluded.precio_centavos,
                   costo_referencia_centavos = excluded.costo_referencia_centavos""",
            (producto.codigo, producto.nombre, producto.categoria, producto.proveedor_codigo,
             a_centavos(producto.precio), a_centavos(producto.costo_referencia)),
        )

    def _cargar_productos(self) -> dict[str, Producto]:
        filas = self._conexion.consultar("SELECT * FROM productos ORDER BY codigo")
        return {
            fila["codigo"]: Producto(
                fila["codigo"], fila["nombre"], fila["categoria"], fila["proveedor_codigo"],
                desde_centavos(fila["precio_centavos"]), desde_centavos(fila["costo_referencia_centavos"]),
            )
            for fila in filas
        }

    # --- Sucursales y existencias ---

    def guardar_sucursal(self, sucursal: Sucursal) -> None:
        """Alta o actualización del nombre. El indicador de CD no se cambia después del alta."""
        self._conexion.ejecutar(
            """INSERT INTO sucursales (codigo, nombre, es_cd) VALUES (?, ?, ?)
               ON CONFLICT (codigo) DO UPDATE SET nombre = excluded.nombre""",
            (sucursal.codigo, sucursal.nombre, int(sucursal.es_cd)),
        )

    def guardar_existencias(self, sucursal: Sucursal) -> None:
        """Guarda disponible y mínimo de todas las existencias del establecimiento."""
        self._conexion.ejecutar_varios(
            """INSERT INTO existencias (sucursal_codigo, producto_codigo, cantidad, minimo)
               VALUES (?, ?, ?, ?)
               ON CONFLICT (sucursal_codigo, producto_codigo) DO UPDATE SET
                   cantidad = excluded.cantidad,
                   minimo = excluded.minimo""",
            [(sucursal.codigo, e.producto.codigo, e.cantidad, e.minimo) for e in sucursal.existencias],
        )

    def cargar_catalogo(self) -> tuple[dict[str, Producto], dict[str, Sucursal]]:
        """Productos y establecimientos (con sus existencias) para usar en una solicitud."""
        productos = self._cargar_productos()
        sucursales = {
            fila["codigo"]: Sucursal(fila["codigo"], fila["nombre"], bool(fila["es_cd"]))
            for fila in self._conexion.consultar("SELECT * FROM sucursales ORDER BY codigo")
        }
        for fila in self._conexion.consultar("SELECT * FROM existencias"):
            sucursales[fila["sucursal_codigo"]].agregar_existencia(
                productos[fila["producto_codigo"]], fila["cantidad"], fila["minimo"]
            )
        return productos, sucursales

    def listar_catalogos(self) -> dict[str, list[dict]]:
        """Filas planas de los tres catálogos, para la grilla de la interfaz."""
        return {
            "proveedores": self.listar_proveedores(),
            "sucursales": [
                {"codigo": f["codigo"], "nombre": f["nombre"], "es_cd": bool(f["es_cd"])}
                for f in self._conexion.consultar("SELECT * FROM sucursales ORDER BY codigo")
            ],
            "productos": [
                {
                    "codigo": f["codigo"], "nombre": f["nombre"], "categoria": f["categoria"],
                    "proveedor_codigo": f["proveedor_codigo"],
                    "precio": desde_centavos(f["precio_centavos"]),
                    "costo_referencia": desde_centavos(f["costo_referencia_centavos"]),
                }
                for f in self._conexion.consultar("SELECT * FROM productos ORDER BY codigo")
            ],
        }

    def consultar_existencias(self, sucursal_codigo: str | None = None,
                              producto_codigo: str | None = None) -> list[dict]:
        filas = self._conexion.consultar(
            """SELECT e.sucursal_codigo, s.nombre AS sucursal_nombre,
                      e.producto_codigo, p.nombre AS producto_nombre,
                      e.cantidad AS disponible, e.minimo,
                      MAX(0, e.minimo - e.cantidad) AS faltante
               FROM existencias e
               JOIN sucursales s ON s.codigo = e.sucursal_codigo
               JOIN productos p ON p.codigo = e.producto_codigo
               WHERE (:sucursal IS NULL OR e.sucursal_codigo = :sucursal)
                 AND (:producto IS NULL OR e.producto_codigo = :producto)
               ORDER BY e.sucursal_codigo, e.producto_codigo""",
            {"sucursal": sucursal_codigo, "producto": producto_codigo},
        )
        return [dict(fila) for fila in filas]

    # --- Ingresos al CD ---

    def insertar_ingreso(self, ingreso: IngresoStock) -> None:
        self._conexion.ejecutar(
            """INSERT INTO ingresos_stock (numero, fecha, producto_codigo, proveedor_codigo,
                                           cantidad, costo_unitario_centavos)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ingreso.numero, fecha_a_texto(ingreso.fecha), ingreso.producto.codigo,
             ingreso.proveedor_codigo, ingreso.cantidad, a_centavos(ingreso.costo_unitario)),
        )

    def buscar_ingreso(self, numero: str, productos: dict[str, Producto]) -> IngresoStock | None:
        fila = self._conexion.consultar_uno("SELECT * FROM ingresos_stock WHERE numero = ?", (numero,))
        if fila is None:
            return None
        return IngresoStock(
            fila["numero"], productos[fila["producto_codigo"]], fila["proveedor_codigo"],
            fila["cantidad"], desde_centavos(fila["costo_unitario_centavos"]), texto_a_fecha(fila["fecha"]),
        )
