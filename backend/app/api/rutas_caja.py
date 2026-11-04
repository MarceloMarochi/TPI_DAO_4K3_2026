"""Rutas del área Caja: medios de pago, ventas y devoluciones."""

from fastapi import APIRouter, Depends

from app.api import esquemas as e
from app.api.adaptador import RESPUESTAS_ERROR, obtener_sistema
from app.negocio.sistema import SistemaVentas

router = APIRouter(prefix="/api", tags=["Caja"], responses=RESPUESTAS_ERROR)


@router.get("/medios-pago", response_model=list[e.MedioPago])
def medios_pago(sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.consultar_medios_pago()


@router.post("/ventas/cotizacion", response_model=e.Cotizacion)
def cotizar(datos: e.CotizacionEntrada, sistema: SistemaVentas = Depends(obtener_sistema)):
    """Calcula subtotal, ajuste del medio de pago y total. No guarda ni reserva stock."""
    return sistema.cotizar_venta(datos.model_dump())


@router.post("/ventas", response_model=e.Venta, status_code=201)
def confirmar_venta(datos: e.VentaEntrada, sistema: SistemaVentas = Depends(obtener_sistema)):
    """Recalcula en el servidor, descuenta stock y registra el cobro en una sola transacción."""
    return sistema.confirmar_venta(datos.model_dump())


@router.get("/ventas", response_model=list[e.VentaResumen])
def listar_ventas(local: str | None = None, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.listar_ventas(local)


@router.get("/ventas/{numero}", response_model=e.Venta)
def consultar_venta(numero: str, sistema: SistemaVentas = Depends(obtener_sistema)):
    """Incluye por línea lo ya devuelto y lo que todavía se puede devolver."""
    return sistema.consultar_venta(numero)


@router.post("/devoluciones", response_model=e.Devolucion, status_code=201)
def devolver(datos: e.DevolucionEntrada, sistema: SistemaVentas = Depends(obtener_sistema)):
    """Una línea por devolución. Reintegra por el medio original; sólo lo apto vuelve al disponible."""
    return sistema.devolver(datos.model_dump())


@router.get("/devoluciones/{numero}", response_model=e.Devolucion)
def consultar_devolucion(numero: str, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.consultar_devolucion(numero)
