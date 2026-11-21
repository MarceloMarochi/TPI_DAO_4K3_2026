"""Caso de uso de importación CSV: lee el archivo y delega las filas en el catálogo."""
from __future__ import annotations

from pathlib import Path
from app.datos.carga_csv import leer_csv
from app.negocio.servicio_catalogo import ServicioCatalogo


class ServicioImportacion:
    """Separa la lectura del archivo de las reglas: éstas son las mismas del alta manual."""

    def __init__(self, catalogo: ServicioCatalogo):
        self._servicio_catalogo = catalogo

    def importar_csv(self, tipo: str, ruta: str | Path) -> dict:
        """Valida todas las filas; si alguna falla no se importa ninguna (una sola transacción).

        tipo: proveedores | sucursales | productos | ingresos | minimos
        El stock inicial se carga como ingresos al CD; nunca directo en un local.
        """
        filas = leer_csv(ruta, tipo)
        importadas = self._servicio_catalogo.importar_filas(tipo, filas)
        return {"tipo": tipo, "filas_importadas": importadas}
