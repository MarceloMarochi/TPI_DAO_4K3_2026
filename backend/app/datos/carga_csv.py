"""Lectura de archivos CSV con el módulo nativo csv.

Sólo lee y valida la estructura (encabezado y cantidad de columnas). Las reglas
de negocio de cada fila las aplica SistemaVentas antes de guardar.
"""

import csv
from pathlib import Path

from app.negocio.errores import ErrorImportacion

# Columnas esperadas por tipo de archivo, en cualquier orden.
COLUMNAS = {
    "proveedores": ["codigo", "nombre"],
    "sucursales": ["codigo", "nombre", "es_cd"],
    "productos": ["codigo", "nombre", "categoria", "proveedor_codigo", "precio", "costo_referencia"],
    "ingresos": ["numero", "producto_codigo", "proveedor_codigo", "cantidad", "costo_unitario"],
    "minimos": ["sucursal_codigo", "producto_codigo", "minimo"],
}


def leer_csv(ruta: str | Path, tipo: str) -> list[tuple[int, dict[str, str]]]:
    """Devuelve (número de fila, {columna: texto}) por cada fila con datos.

    Acepta coma o punto y coma como separador (Excel en español usa punto y coma).
    La fila 1 es el encabezado; las filas vacías se ignoran.
    """
    if tipo not in COLUMNAS:
        raise ErrorImportacion([{"fila": None, "campo": "tipo", "mensaje": f"tipo de archivo desconocido: {tipo}"}])
    esperadas = COLUMNAS[tipo]

    with open(ruta, newline="", encoding="utf-8-sig") as archivo:
        primera_linea = archivo.readline()
        archivo.seek(0)
        separador = ";" if primera_linea.count(";") > primera_linea.count(",") else ","
        lector = csv.reader(archivo, delimiter=separador)

        encabezado = next(lector, None)
        if encabezado is None:
            raise ErrorImportacion([{"fila": 1, "campo": None, "mensaje": "el archivo está vacío"}])
        encabezado = [columna.strip().lower() for columna in encabezado]
        faltantes = [c for c in esperadas if c not in encabezado]
        sobrantes = [c for c in encabezado if c not in esperadas]
        if faltantes or sobrantes or len(set(encabezado)) != len(encabezado):
            raise ErrorImportacion([{
                "fila": 1, "campo": None,
                "mensaje": f"encabezado inválido; se esperaba: {', '.join(esperadas)}",
            }])

        filas = []
        errores = []
        for numero_fila, valores in enumerate(lector, start=2):
            if not any(valor.strip() for valor in valores):
                continue
            if len(valores) != len(encabezado):
                errores.append({
                    "fila": numero_fila, "campo": None,
                    "mensaje": f"tiene {len(valores)} columnas y se esperaban {len(encabezado)}",
                })
                continue
            filas.append((numero_fila, {col: valor.strip() for col, valor in zip(encabezado, valores)}))

    if errores:
        raise ErrorImportacion(errores)
    if not filas:
        raise ErrorImportacion([{"fila": None, "campo": None, "mensaje": "el archivo no tiene filas de datos"}])
    return filas
