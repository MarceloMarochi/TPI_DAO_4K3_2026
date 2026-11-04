"""Rutas del área Catálogos y stock."""

import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Request, UploadFile

from app.api import esquemas as e
from app.api.adaptador import RESPUESTAS_ERROR, obtener_sistema
from app.negocio.errores import ErrorImportacion
from app.negocio.sistema import SistemaVentas

router = APIRouter(prefix="/api", tags=["Catálogos y stock"], responses=RESPUESTAS_ERROR)

TAMANIO_MAXIMO_CSV = 2 * 1024 * 1024  # 2 MB


# --- Proveedores ---

@router.get("/proveedores", response_model=list[e.Proveedor])
def listar_proveedores(sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.consultar_catalogo("proveedor")


@router.post("/proveedores", response_model=e.Proveedor, status_code=201)
def alta_proveedor(datos: e.Proveedor, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.guardar_catalogo("proveedor", datos.model_dump(), alta=True)


@router.put("/proveedores/{codigo}", response_model=e.Proveedor)
def editar_proveedor(codigo: str, datos: e.ProveedorEdicion, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.guardar_catalogo("proveedor", datos.model_dump() | {"codigo": codigo}, alta=False)


# --- Sucursales ---

@router.get("/sucursales", response_model=list[e.Sucursal])
def listar_sucursales(sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.consultar_catalogo("sucursal")


@router.post("/sucursales", response_model=e.Sucursal, status_code=201)
def alta_sucursal(datos: e.SucursalAlta, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.guardar_catalogo("sucursal", datos.model_dump(), alta=True)


@router.put("/sucursales/{codigo}", response_model=e.Sucursal)
def editar_sucursal(codigo: str, datos: e.SucursalEdicion, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.guardar_catalogo("sucursal", datos.model_dump() | {"codigo": codigo}, alta=False)


# --- Productos ---

@router.get("/productos", response_model=list[e.Producto])
def listar_productos(sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.consultar_catalogo("producto")


@router.post("/productos", response_model=e.Producto, status_code=201)
def alta_producto(datos: e.ProductoAlta, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.guardar_catalogo("producto", datos.model_dump(), alta=True)


@router.put("/productos/{codigo}", response_model=e.Producto)
def editar_producto(codigo: str, datos: e.ProductoEdicion, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.guardar_catalogo("producto", datos.model_dump() | {"codigo": codigo}, alta=False)


# --- Existencias ---

@router.get("/existencias", response_model=list[e.Existencia])
def consultar_existencias(sucursal: str | None = None, producto: str | None = None,
                          sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.consultar_existencias(sucursal, producto)


@router.put("/existencias/{sucursal}/{producto}/minimo", response_model=e.Existencia)
def configurar_minimo(sucursal: str, producto: str, datos: e.MinimoEntrada,
                      sistema: SistemaVentas = Depends(obtener_sistema)):
    """Sólo el mínimo es editable; el disponible cambia únicamente por operaciones."""
    return sistema.configurar_minimo(sucursal, producto, datos.minimo)


# --- Ingresos al CD ---

@router.post("/ingresos", response_model=e.Ingreso, status_code=201)
def registrar_ingreso(datos: e.IngresoEntrada, sistema: SistemaVentas = Depends(obtener_sistema)):
    """Entrada de compra al CD. La fecha la asigna el servidor."""
    return sistema.registrar_ingreso(datos.model_dump())


@router.get("/ingresos/{numero}", response_model=e.Ingreso)
def consultar_ingreso(numero: str, sistema: SistemaVentas = Depends(obtener_sistema)):
    return sistema.consultar_ingreso(numero)


# --- Importación CSV ---

@router.post("/importaciones/{tipo}", response_model=e.ResultadoImportacion)
async def importar_csv(tipo: Literal["proveedores", "sucursales", "productos", "ingresos", "minimos"],
                       archivo: UploadFile, request: Request,
                       sistema: SistemaVentas = Depends(obtener_sistema)):
    """Sube un CSV. Se guarda en una carpeta temporal del servidor (el nombre del usuario
    nunca se usa como ruta) y se importa completo o no se importa nada."""
    contenido = await archivo.read(TAMANIO_MAXIMO_CSV + 1)
    if len(contenido) > TAMANIO_MAXIMO_CSV:
        raise ErrorImportacion([{"fila": None, "campo": "archivo", "mensaje": "el archivo supera los 2 MB"}])

    carpeta = Path(request.app.state.directorio_temporal)
    carpeta.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=carpeta, suffix=".csv", delete=False) as temporal:
        temporal.write(contenido)
        ruta = Path(temporal.name)
    try:
        return sistema.importar_csv(tipo, ruta)
    finally:
        ruta.unlink(missing_ok=True)
