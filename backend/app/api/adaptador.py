"""Piezas comunes del adaptador HTTP (AdaptadorAPI en el diseño).

- obtener_sistema: crea una conexión y un SistemaVentas por solicitud y los cierra al terminar.
- registrar_manejadores: traduce los errores de negocio a respuestas HTTP uniformes
  {codigo, mensaje, detalles}.

    ValueError         -> 422 DATO_INVALIDO
    ErrorImportacion   -> 422 IMPORTACION_INVALIDA (con errores por fila)
    NoEncontrado       -> 404 NO_ENCONTRADO
    Conflicto          -> 409 CONFLICTO
    IntegrityError     -> 409 CONFLICTO (respaldo de las restricciones UNIQUE / FK de SQLite)
"""

import sqlite3

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.esquemas import Error
from app.datos.conexion import ConexionSQLite
from app.negocio.errores import Conflicto, ErrorImportacion, NoEncontrado
from app.negocio.sistema import SistemaVentas

# Respuestas de error documentadas en OpenAPI para cada ruta.
RESPUESTAS_ERROR = {
    404: {"model": Error, "description": "Recurso inexistente"},
    409: {"model": Error, "description": "Conflicto de stock, estado, unicidad o cotización"},
    422: {"model": Error, "description": "Datos inválidos"},
}


def obtener_sistema(request: Request):
    """Dependencia de FastAPI: un coordinador y una conexión por solicitud, nunca compartidos."""
    app = request.app
    conexion = ConexionSQLite(app.state.ruta_base_datos)
    try:
        yield SistemaVentas(conexion, app.state.descuento_efectivo, app.state.recargo_tarjeta)
    finally:
        conexion.cerrar()


def _respuesta(estado: int, codigo: str, mensaje: str, detalles: list | None = None) -> JSONResponse:
    return JSONResponse(status_code=estado,
                        content={"codigo": codigo, "mensaje": mensaje, "detalles": detalles or []})


def _campo(mensaje: str) -> str | None:
    if ":" in mensaje and mensaje[:1].islower():
        return mensaje.split(":", 1)[0]
    return None


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(NoEncontrado)
    async def no_encontrado(_: Request, error: NoEncontrado):
        return _respuesta(404, "NO_ENCONTRADO", str(error))

    @app.exception_handler(Conflicto)
    async def conflicto(_: Request, error: Conflicto):
        return _respuesta(409, "CONFLICTO", str(error))

    @app.exception_handler(ErrorImportacion)
    async def importacion(_: Request, error: ErrorImportacion):
        return _respuesta(422, "IMPORTACION_INVALIDA", str(error), error.errores)

    @app.exception_handler(ValueError)
    async def dato_invalido(_: Request, error: ValueError):
        mensaje = str(error)
        return _respuesta(422, "DATO_INVALIDO", mensaje, [{"campo": _campo(mensaje), "mensaje": mensaje}])

    @app.exception_handler(sqlite3.IntegrityError)
    async def integridad(_: Request, error: sqlite3.IntegrityError):
        return _respuesta(409, "CONFLICTO", "El registro ya existe o referencia datos inexistentes",
                          [{"mensaje": str(error)}])

    @app.exception_handler(RequestValidationError)
    async def estructura_invalida(_: Request, error: RequestValidationError):
        detalles = [
            {"campo": ".".join(str(parte) for parte in e["loc"] if parte != "body"), "mensaje": e["msg"]}
            for e in error.errors()
        ]
        return _respuesta(422, "DATO_INVALIDO", "La solicitud tiene datos inválidos", detalles)
