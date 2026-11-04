"""Crea la base SQLite y, opcionalmente, carga los datos de ejemplo.

Uso (desde la carpeta backend):

    python -m app.inicializar            crea las tablas si no existen
    python -m app.inicializar --demo     además importa los CSV de datos_ejemplo/
    python -m app.inicializar --demo --desde-cero
                                         borra la base existente y la vuelve a crear
"""

import argparse
import sys
from pathlib import Path

from app import config
from app.datos.conexion import ConexionSQLite
from app.negocio.errores import ErrorImportacion
from app.negocio.sistema import SistemaVentas

CARPETA_EJEMPLO = config.DIRECTORIO_BACKEND / "datos_ejemplo"

# El orden importa: cada archivo referencia datos de los anteriores.
ARCHIVOS_EJEMPLO = [
    ("proveedores", "proveedores.csv"),
    ("sucursales", "sucursales.csv"),
    ("productos", "productos.csv"),
    ("ingresos", "ingresos.csv"),
    ("minimos", "minimos.csv"),
]


def inicializar(ruta: Path, demo: bool = False, desde_cero: bool = False) -> None:
    if desde_cero and ruta.exists():
        ruta.unlink()
        print(f"Base anterior eliminada: {ruta}")

    with ConexionSQLite(ruta) as conexion:
        conexion.crear_esquema()
        print(f"Esquema listo en {ruta}")
        if demo:
            sistema = SistemaVentas(conexion)
            for tipo, archivo in ARCHIVOS_EJEMPLO:
                resultado = sistema.importar_csv(tipo, CARPETA_EJEMPLO / archivo)
                print(f"  {tipo}: {resultado['filas_importadas']} filas")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows no usa UTF-8 por defecto
    parser = argparse.ArgumentParser(description="Inicializa la base de datos del sistema de ventas")
    parser.add_argument("--demo", action="store_true", help="importar los CSV de datos_ejemplo/")
    parser.add_argument("--desde-cero", action="store_true", help="borrar la base existente antes de crearla")
    parser.add_argument("--ruta", type=Path, default=config.RUTA_BASE_DATOS, help="archivo SQLite a usar")
    argumentos = parser.parse_args()
    try:
        inicializar(argumentos.ruta, argumentos.demo, argumentos.desde_cero)
    except ErrorImportacion as error:
        print(error)
        for detalle in error.errores:
            print(f"  fila {detalle['fila']}: {detalle['mensaje']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
