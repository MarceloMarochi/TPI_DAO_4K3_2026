"""Aplicación FastAPI.

Ejecutar desde la carpeta backend:

    uvicorn app.main:app --reload

Documentación interactiva en http://localhost:8000/docs y contrato en /openapi.json.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app import config
from app.api import rutas_caja, rutas_catalogo, rutas_logistica, rutas_reportes
from app.api.adaptador import registrar_manejadores
from app.datos.conexion import ConexionSQLite
from app.negocio.pagos import Efectivo, Tarjeta


def create_app(ruta_base_datos: str | Path = config.RUTA_BASE_DATOS,
               descuento_efectivo=config.TASA_DESCUENTO_EFECTIVO,
               recargo_tarjeta=config.TASA_RECARGO_TARJETA,
               directorio_temporal: str | Path = config.DIRECTORIO_TEMPORAL) -> FastAPI:

    # Las tasas se validan al iniciar: si están mal configuradas, el servidor no arranca.
    Efectivo(descuento_efectivo)
    Tarjeta(recargo_tarjeta)

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        with ConexionSQLite(app.state.ruta_base_datos) as conexion:
            conexion.crear_esquema()  # idempotente: CREATE ... IF NOT EXISTS
        yield

    app = FastAPI(
        title="Sistema de Ventas e Inventario",
        description="Centro de Distribución a Locales · TP Integrador DAO 2026 · Grupo G-029",
        version="0.5.0",
        lifespan=ciclo_de_vida,
    )
    app.state.ruta_base_datos = str(ruta_base_datos)
    app.state.descuento_efectivo = descuento_efectivo
    app.state.recargo_tarjeta = recargo_tarjeta
    app.state.directorio_temporal = str(directorio_temporal)

    # En desarrollo Vite redirige /api al backend; CORS sólo permite el servidor de Vite por si
    # alguien llama directo desde el navegador.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    registrar_manejadores(app)
    app.include_router(rutas_catalogo.router)
    app.include_router(rutas_logistica.router)
    app.include_router(rutas_caja.router)
    app.include_router(rutas_reportes.router)

    @app.get("/api/salud", tags=["General"])
    def salud():
        return {"estado": "ok"}

    @app.get("/", include_in_schema=False)
    def raiz():
        # Hasta que el backend sirva el frontend compilado (fase 7), la raíz lleva a la documentación.
        return RedirectResponse("/docs")

    return app


app = create_app()
