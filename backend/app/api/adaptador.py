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


# Pydantic informa los errores de estructura en inglés. Se traducen por tipo de error;
# los que no están en la tabla conservan el texto original.
_MENSAJES_VALIDACION = {
    "missing": "es obligatorio",
    "extra_forbidden": "no es un dato admitido",
    "decimal_parsing": "debe ser un número; usá punto para los decimales (por ejemplo 1500.50)",
    "decimal_type": "debe ser un número; usá punto para los decimales (por ejemplo 1500.50)",
    "finite_number": "debe ser un número finito",
    "decimal_max_places": "admite como máximo {decimal_places} decimales",
    "decimal_max_digits": "tiene demasiados dígitos",
    "decimal_whole_digits": "tiene demasiados dígitos",
    "int_type": "debe ser un número entero",
    "int_parsing": "debe ser un número entero",
    "int_from_float": "debe ser un número entero",
    "greater_than": "debe ser mayor que {gt}",
    "greater_than_equal": "debe ser mayor o igual que {ge}",
    "less_than": "debe ser menor que {lt}",
    "less_than_equal": "debe ser menor o igual que {le}",
    "string_type": "debe ser un texto",
    "string_too_short": "no puede estar vacío",
    "bool_type": "debe ser sí o no",
    "bool_parsing": "debe ser sí o no",
    "list_type": "debe ser una lista",
    "too_short": "debe tener al menos {min_length} elemento(s)",
    "date_type": "debe ser una fecha con formato AAAA-MM-DD",
    "date_parsing": "debe ser una fecha con formato AAAA-MM-DD",
    "date_from_datetime_parsing": "debe ser una fecha con formato AAAA-MM-DD",
    "date_from_datetime_inexact": "debe ser una fecha con formato AAAA-MM-DD",
    "literal_error": "debe ser uno de estos valores: {expected}",
    "enum": "debe ser uno de estos valores: {expected}",
    "model_type": "tiene un formato inválido",
    "dict_type": "tiene un formato inválido",
    "model_attributes_type": "tiene un formato inválido",
    "json_invalid": "el contenido no es JSON válido",
}

# Partes de la ubicación del error que no son nombres de campo.
_UBICACIONES = {"body", "query", "path", "header"}


def _detalle_validacion(error: dict) -> dict:
    """Arma {campo, mensaje} en castellano a partir de un error de Pydantic.

    items.0.cantidad -> campo "items.0.cantidad", mensaje "cantidad (línea 1): debe ser ..."
    """
    partes = [p for p in error["loc"] if p not in _UBICACIONES]
    campo = ".".join(str(p) for p in partes) or None

    tipo = error.get("type", "")
    if tipo == "value_error":  # validadores propios: el texto ya está en castellano
        texto = str((error.get("ctx") or {}).get("error") or error["msg"])
    elif tipo in _MENSAJES_VALIDACION:
        contexto = dict(error.get("ctx") or {})
        if "expected" in contexto:  # "'a', 'b' or 'c'" -> "'a', 'b' o 'c'"
            contexto["expected"] = str(contexto["expected"]).replace(" or ", " o ")
        try:
            texto = _MENSAJES_VALIDACION[tipo].format(**contexto)
        except (KeyError, IndexError):
            texto = error["msg"]
    else:
        texto = error["msg"]

    nombres = [str(p) for p in partes if not isinstance(p, int)]
    lineas = [p for p in partes if isinstance(p, int)]
    etiqueta = nombres[-1] if nombres else None
    if etiqueta and lineas:
        etiqueta = f"{etiqueta} (línea {lineas[-1] + 1})"
    mensaje = f"{etiqueta}: {texto}" if etiqueta and not texto.startswith(f"{nombres[-1]}:") else texto
    return {"campo": campo, "mensaje": mensaje}


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
        detalles = [_detalle_validacion(e) for e in error.errors()]
        return _respuesta(422, "DATO_INVALIDO", "La solicitud tiene datos inválidos", detalles)
