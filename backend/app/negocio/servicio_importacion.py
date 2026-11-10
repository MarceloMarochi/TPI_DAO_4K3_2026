"""Casos de uso de importacion del alcance simplificado."""
from __future__ import annotations

from pathlib import Path
from app.negocio.errores import ErrorImportacion
from app.negocio.conversiones import _error_de_fila
from app.datos.carga_csv import leer_csv
from app.negocio.servicio_catalogo import ServicioCatalogo


class ServicioImportacion:
    def __init__(self, catalogo: ServicioCatalogo):
        self._servicio_catalogo = catalogo

    def importar_csv(self, tipo: str, ruta: str | Path) -> dict:
        """Valida todas las filas; si alguna falla no se importa ninguna (una sola transacción).

        tipo: proveedores | sucursales | productos | ingresos | minimos
        El stock inicial se carga como ingresos al CD; nunca directo en un local.
        """
        filas = leer_csv(ruta, tipo)
        with self._servicio_catalogo._escritura():
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
            self._servicio_catalogo._guardar_proveedor(fila, alta=True)
        elif tipo == "sucursales":
            self._servicio_catalogo._guardar_sucursal(fila, alta=True)
        elif tipo == "productos":
            self._servicio_catalogo._guardar_producto(fila, alta=True)
        elif tipo == "ingresos":
            self._servicio_catalogo._registrar_ingreso(fila)
        elif tipo == "minimos":
            self._servicio_catalogo._configurar_minimo(fila.get("sucursal_codigo"), fila.get("producto_codigo"), fila.get("minimo"))
