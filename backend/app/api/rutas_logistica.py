"""Rutas del área Logística: órdenes de reposición y bultos.

Las acciones del bulto no deciden nada: SistemaVentas delega en el estado del bulto
(patrón State), que acepta o rechaza la operación. La respuesta incluye las
acciones permitidas para que la interfaz sepa qué botones mostrar.
"""

from fastapi import APIRouter, Depends

from app.api import esquemas as e
from app.api.adaptador import RESPUESTAS_ERROR, obtener_sistema
from app.negocio.sistema import SistemaVentas

router = APIRouter(prefix="/api", tags=["Logística"], responses=RESPUESTAS_ERROR)


# --- Órdenes de reposición ---

@router.get("/ordenes", response_model=list[e.OrdenResumen])
def listar_ordenes(pendientes: bool = False, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.listar_ordenes(solo_con_pendientes=pendientes)


@router.post("/ordenes", response_model=e.Orden, status_code=201)
def crear_orden(datos: e.OrdenEntrada, sistema: SistemaVentas = Depends(obtener_sistema)):
    """Consolida necesidades de los locales; mismo producto y destino se suman en una línea."""
    return sistema.crear_orden(datos.model_dump())


@router.get("/ordenes/{numero}", response_model=e.Orden)
def consultar_orden(numero: str, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.consultar_orden(numero)


# --- Bultos ---

@router.get("/bultos", response_model=list[e.BultoResumen])
def listar_bultos(estado: str | None = None, destino: str | None = None,
                  sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.listar_bultos(estado, destino)


@router.post("/bultos", response_model=e.Bulto, status_code=201)
def preparar_bulto(datos: e.BultoEntrada, sistema: SistemaVentas = Depends(obtener_sistema)):
    """Crea el bulto en estado PREPARADO y descuenta el disponible del CD (una única vez)."""
    return sistema.preparar_bulto(datos.model_dump())


@router.get("/bultos/{codigo}", response_model=e.Bulto)
def consultar_bulto(codigo: str, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.consultar_bulto(codigo)


@router.post("/bultos/{codigo}/precintar", response_model=e.Bulto)
def precintar(codigo: str, datos: e.PrecintarEntrada, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.precintar(codigo, datos.numero)


@router.post("/bultos/{codigo}/despachar", response_model=e.Bulto)
def despachar(codigo: str, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.despachar(codigo)


@router.post("/bultos/{codigo}/recibir", response_model=e.Bulto)
def recibir(codigo: str, datos: e.RecibirEntrada, sistema: SistemaVentas = Depends(obtener_sistema)):
    """Con precinto roto (intacto=false) el bulto pasa a RECHAZADO y el motivo es obligatorio."""
    return sistema.recibir(codigo, datos.intacto, datos.motivo)


@router.post("/bultos/{codigo}/verificar", response_model=e.Bulto)
def verificar(codigo: str, datos: e.VerificarEntrada, sistema: SistemaVentas = Depends(obtener_sistema)):
    """Sólo una verificación conforme habilita el stock para la venta en el local."""
    return sistema.verificar(codigo, datos.conforme, datos.motivo)
