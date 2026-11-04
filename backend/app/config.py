"""Configuración del servidor.

Las tasas se validan al construir los medios de pago (ver negocio/pagos.py).
"""

from decimal import Decimal
from pathlib import Path

DIRECTORIO_BACKEND = Path(__file__).resolve().parent.parent

# Base SQLite del servidor. Nunca se accede desde el navegador.
RUTA_BASE_DATOS = DIRECTORIO_BACKEND / "ventas.sqlite3"

# Archivos subidos (CSV) mientras se procesan; se borran al terminar.
DIRECTORIO_TEMPORAL = DIRECTORIO_BACKEND / "tmp"

# TODO(grupo): tasas provisorias propuestas en el documento maestro (P-04).
# Definir los valores finales a criterio del grupo.
TASA_DESCUENTO_EFECTIVO = Decimal("0.10")  # 10 % de descuento; 0 <= tasa < 1
TASA_RECARGO_TARJETA = Decimal("0.10")  # 10 % de recargo; tasa >= 0
