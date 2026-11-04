"""Rutas del área Reportes y del comprobante de venta.

Cada reporte se consulta en JSON y se descarga en PDF con los MISMOS filtros:
ambos usan el resultado de SistemaVentas.consultar_reporte.
"""

from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api import esquemas as e
from app.api.adaptador import RESPUESTAS_ERROR, obtener_sistema
from app.negocio.sistema import SistemaVentas
from app.presentacion.exportador_pdf import ExportadorPDF

router = APIRouter(prefix="/api", tags=["Reportes"], responses=RESPUESTAS_ERROR)

RESPUESTA_PDF = {200: {"content": {"application/pdf": {}}, "description": "Documento PDF"}}


def _pdf(contenido: bytes, nombre_archivo: str) -> Response:
    return Response(contenido, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'})


def _reporte_pdf(sistema: SistemaVentas, nombre: str, filtros: dict) -> Response:
    datos = sistema.consultar_reporte(nombre, filtros)
    return _pdf(ExportadorPDF().exportar_reporte(datos), f"reporte-{nombre}-{datos['generado']:%Y%m%d-%H%M}.pdf")


# --- R1 Ventas e ingresos ---

@router.get("/reportes/ventas", response_model=e.ReporteVentas)
def reporte_ventas(desde: date, hasta: date, local: str | None = None, medio: str | None = None,
                   sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.consultar_reporte("ventas", {"desde": desde, "hasta": hasta, "local": local, "medio": medio})


@router.get("/reportes/ventas/pdf", response_class=Response, responses=RESPUESTA_PDF)
def reporte_ventas_pdf(desde: date, hasta: date, local: str | None = None, medio: str | None = None,
                       sistema: SistemaVentas = Depends(obtener_sistema)):
    """Incluye el gráfico de ingreso neto por local (Matplotlib)."""
    return _reporte_pdf(sistema, "ventas", {"desde": desde, "hasta": hasta, "local": local, "medio": medio})


# --- R2 Productos vendidos y margen ---

@router.get("/reportes/productos", response_model=e.ReporteProductos)
def reporte_productos(desde: date, hasta: date, local: str | None = None,
                      sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.consultar_reporte("productos", {"desde": desde, "hasta": hasta, "local": local})


@router.get("/reportes/productos/pdf", response_class=Response, responses=RESPUESTA_PDF)
def reporte_productos_pdf(desde: date, hasta: date, local: str | None = None,
                          sistema: SistemaVentas = Depends(obtener_sistema)):
    return _reporte_pdf(sistema, "productos", {"desde": desde, "hasta": hasta, "local": local})


# --- R3 Existencias y mínimos (corte actual, sin período) ---

@router.get("/reportes/existencias", response_model=e.ReporteExistencias)
def reporte_existencias(sucursal: str | None = None, producto: str | None = None, solo_bajo_minimo: bool = False,
                        sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.consultar_reporte("existencias", {"sucursal": sucursal, "producto": producto,
                                                     "solo_bajo_minimo": solo_bajo_minimo or None})


@router.get("/reportes/existencias/pdf", response_class=Response, responses=RESPUESTA_PDF)
def reporte_existencias_pdf(sucursal: str | None = None, producto: str | None = None,
                            solo_bajo_minimo: bool = False, sistema: SistemaVentas = Depends(obtener_sistema)):
    return _reporte_pdf(sistema, "existencias", {"sucursal": sucursal, "producto": producto,
                                                 "solo_bajo_minimo": solo_bajo_minimo or None})


# --- R4 Rechazos de bultos ---

@router.get("/reportes/rechazos", response_model=e.ReporteRechazos)
def reporte_rechazos(desde: date, hasta: date, destino: str | None = None,
                     sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.consultar_reporte("rechazos", {"desde": desde, "hasta": hasta, "destino": destino})


@router.get("/reportes/rechazos/pdf", response_class=Response, responses=RESPUESTA_PDF)
def reporte_rechazos_pdf(desde: date, hasta: date, destino: str | None = None,
                         sistema: SistemaVentas = Depends(obtener_sistema)):
    return _reporte_pdf(sistema, "rechazos", {"desde": desde, "hasta": hasta, "destino": destino})


# --- Comprobante interno de venta ---

@router.get("/ventas/{numero}/comprobante", response_class=Response, responses=RESPUESTA_PDF, tags=["Caja"])
def comprobante(numero: str, sistema: SistemaVentas = Depends(obtener_sistema)):
    venta = sistema.consultar_venta(numero)
    return _pdf(ExportadorPDF().emitir_comprobante(venta), f"comprobante-{venta['comprobante_numero']}.pdf")
