"""Esquemas de los mensajes HTTP (Pydantic).

Describen la forma de las solicitudes y respuestas para validar la estructura y
generar el contrato OpenAPI. NO son las entidades del dominio: las reglas de
negocio se validan en los modelos y en SistemaVentas.

Importes y tasas viajan como texto decimal ("1000.00"); fechas en ISO 8601 con zona.
"""

from datetime import date, datetime
from decimal import Decimal

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.negocio.comunes import validar_total_esperado

CantidadPositiva = Annotated[int, Field(strict=True, gt=0)]
MinimoNoNegativo = Annotated[int, Field(strict=True, ge=0)]


class Esquema(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------


class DetalleError(BaseModel):
    fila: int | None = None
    campo: str | None = None
    mensaje: str


class Error(BaseModel):
    codigo: str = Field(examples=["CONFLICTO"])
    mensaje: str = Field(examples=["Stock insuficiente de P001 en L01: disponible 3, solicitado 5"])
    detalles: list[DetalleError] = []


# ---------------------------------------------------------------------------
# Catálogos y stock
# ---------------------------------------------------------------------------


class ProveedorEdicion(Esquema):
    nombre: str


class Proveedor(ProveedorEdicion):
    codigo: str


class SucursalEdicion(Esquema):
    nombre: str


class SucursalAlta(SucursalEdicion):
    codigo: str
    es_cd: bool = False


class Sucursal(BaseModel):
    codigo: str
    nombre: str
    es_cd: bool


class ProductoEdicion(Esquema):
    nombre: str
    categoria: str
    proveedor_codigo: str
    precio: Decimal
    costo_referencia: Decimal | None = None


class ProductoAlta(ProductoEdicion):
    codigo: str
    costo_referencia: Decimal


class Producto(BaseModel):
    codigo: str
    nombre: str
    categoria: str
    proveedor_codigo: str
    precio: Decimal
    costo_referencia: Decimal


class Existencia(BaseModel):
    sucursal_codigo: str
    sucursal_nombre: str | None = None
    producto_codigo: str
    producto_nombre: str | None = None
    disponible: int
    minimo: int
    faltante: int


class MinimoEntrada(Esquema):
    minimo: MinimoNoNegativo


class IngresoEntrada(Esquema):
    numero: str
    producto_codigo: str
    proveedor_codigo: str
    cantidad: CantidadPositiva
    costo_unitario: Decimal


class Ingreso(BaseModel):
    numero: str
    fecha: datetime
    producto_codigo: str
    proveedor_codigo: str
    cantidad: int
    costo_unitario: Decimal
    importe: Decimal


class ResultadoImportacion(BaseModel):
    tipo: str
    filas_importadas: int


# ---------------------------------------------------------------------------
# Logística
# ---------------------------------------------------------------------------


class NecesidadEntrada(Esquema):
    destino_codigo: str
    producto_codigo: str
    cantidad: CantidadPositiva


class OrdenEntrada(Esquema):
    numero: str
    necesidades: list[NecesidadEntrada]


class DetalleOrden(BaseModel):
    id: int
    destino_codigo: str
    producto_codigo: str
    producto_nombre: str
    solicitado: int
    asignado: int
    pendiente: int


class Orden(BaseModel):
    numero: str
    fecha: datetime
    origen_codigo: str
    cerrada: bool
    detalles: list[DetalleOrden]


class OrdenResumen(BaseModel):
    numero: str
    fecha: datetime
    origen_codigo: str
    cerrada: bool
    solicitado: int
    asignado: int
    pendiente: int


class LineaBultoEntrada(Esquema):
    detalle_id: CantidadPositiva
    cantidad: CantidadPositiva


class BultoEntrada(Esquema):
    codigo: str
    orden_numero: str
    destino_codigo: str
    remito_numero: str
    lineas: list[LineaBultoEntrada]


class PrecintarEntrada(Esquema):
    numero: str


class RecibirEntrada(Esquema):
    intacto: bool
    motivo: str = ""


class VerificarEntrada(Esquema):
    conforme: bool
    motivo: str = ""


class DetalleBulto(BaseModel):
    detalle_id: int
    producto_codigo: str
    producto_nombre: str
    cantidad: int


class CambioEstado(BaseModel):
    secuencia: int
    fecha: datetime
    anterior: str | None
    nuevo: str
    motivo: str


class Bulto(BaseModel):
    codigo: str
    orden_numero: str
    destino_codigo: str
    remito_numero: str
    precinto_numero: str | None
    precinto_intacto: bool | None
    estado: str = Field(examples=["EN_TRANSITO"])
    estado_remito: str = Field(examples=["PENDIENTE"])
    acciones_permitidas: list[str] = Field(examples=[["recibir"]])
    unidades: int
    detalles: list[DetalleBulto]
    historial: list[CambioEstado]


class BultoResumen(BaseModel):
    codigo: str
    orden_numero: str
    destino_codigo: str
    destino_nombre: str
    remito_numero: str
    precinto_numero: str | None
    estado: str
    unidades: int
    fecha_preparacion: datetime
    fecha_ultimo_cambio: datetime


# ---------------------------------------------------------------------------
# Caja
# ---------------------------------------------------------------------------


class MedioPago(BaseModel):
    codigo: str
    tipo: str = Field(examples=["descuento"])
    tasa: Decimal


class ItemVenta(Esquema):
    producto_codigo: str
    cantidad: CantidadPositiva


class CotizacionEntrada(Esquema):
    local_codigo: str
    medio_codigo: str = Field(examples=["EFECTIVO"])
    items: list[ItemVenta]


class VentaEntrada(CotizacionEntrada):
    numero: str
    total_esperado: Decimal = Field(
        ge=0, decimal_places=2, allow_inf_nan=False,
        description="Total obligatorio revisado al cotizar; si cambió, no se guarda la venta (409).",
    )

    @field_validator("total_esperado", mode="before")
    @classmethod
    def validar_total(cls, valor):
        return validar_total_esperado(valor)


class LineaCotizacion(BaseModel):
    producto_codigo: str
    producto_nombre: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal


class Cotizacion(BaseModel):
    local_codigo: str
    medio_codigo: str
    tasa: Decimal
    lineas: list[LineaCotizacion]
    subtotal: Decimal
    ajuste: Decimal
    total: Decimal


class LineaVenta(BaseModel):
    id: int
    producto_codigo: str
    producto_nombre: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal
    importe_cobrado: Decimal
    cantidad_devuelta: int
    importe_devuelto: Decimal
    cantidad_restante: int


class Venta(BaseModel):
    numero: str
    fecha: datetime
    local_codigo: str
    local_nombre: str
    medio_codigo: str
    tasa_aplicada: Decimal
    subtotal: Decimal
    ajuste: Decimal
    total_cobrado: Decimal
    comprobante_numero: str
    lineas: list[LineaVenta]


class VentaResumen(BaseModel):
    numero: str
    fecha: datetime
    local_codigo: str
    local_nombre: str
    medio_codigo: str
    total_cobrado: Decimal
    comprobante_numero: str


class DevolucionEntrada(Esquema):
    numero: str
    venta_numero: str
    detalle_id: CantidadPositiva
    cantidad: CantidadPositiva
    apta_reventa: bool
    motivo: str


class Devolucion(BaseModel):
    numero: str
    fecha: datetime
    venta_numero: str
    detalle_id: int
    producto_codigo: str
    cantidad: int
    apta_reventa: bool
    motivo: str
    importe_reintegrado: Decimal
    medio_codigo: str


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------


class ReporteBase(BaseModel):
    reporte: str
    titulo: str
    generado: datetime
    filtros: dict[str, date | str | bool]


class FilaVentas(BaseModel):
    local_codigo: str
    local_nombre: str
    medio_codigo: str
    cantidad_ventas: int
    cobrado: Decimal
    reintegrado: Decimal
    neto: Decimal


class TotalesVentas(BaseModel):
    cantidad_ventas: int
    cobrado: Decimal
    reintegrado: Decimal
    neto: Decimal


class BarraGrafico(BaseModel):
    local_codigo: str
    local_nombre: str
    neto: Decimal


class ReporteVentas(ReporteBase):
    filas: list[FilaVentas]
    totales: TotalesVentas
    grafico: list[BarraGrafico]


class FilaProductos(BaseModel):
    posicion: int
    producto_codigo: str
    producto_nombre: str
    categoria: str
    vendidas: int
    devueltas: int
    devueltas_aptas: int
    devueltas_no_aptas: int
    unidades_netas: int
    cobrado: Decimal
    reintegrado: Decimal
    importe_neto: Decimal
    costo_vendido: Decimal
    costo_devuelto: Decimal
    costo_neto: Decimal
    margen: Decimal


class TotalesProductos(BaseModel):
    vendidas: int
    devueltas: int
    devueltas_aptas: int
    devueltas_no_aptas: int
    unidades_netas: int
    importe_neto: Decimal
    costo_neto: Decimal
    margen: Decimal


class ReporteProductos(ReporteBase):
    filas: list[FilaProductos]
    totales: TotalesProductos


class FilaExistencias(BaseModel):
    sucursal_codigo: str
    sucursal_nombre: str
    es_cd: bool
    producto_codigo: str
    producto_nombre: str
    disponible: int
    minimo: int
    faltante: int
    bajo_minimo: bool
    comprometido_salida: int
    pendiente_despacho: int
    en_transito: int
    recibido_sin_verificar: int
    rechazado: int
    devuelto_no_apto: int


class TotalesExistencias(BaseModel):
    filas: int
    bajo_minimo: int
    faltante: int
    en_transito: int
    recibido_sin_verificar: int


class ReporteExistencias(ReporteBase):
    filas: list[FilaExistencias]
    totales: TotalesExistencias


class FilaRechazos(BaseModel):
    destino_codigo: str
    destino_nombre: str
    verificados: int
    rechazados: int
    finalizados: int
    porcentaje_rechazo: Decimal | None = Field(description="null cuando no hay bultos finalizados (sin datos)")
    unidades_rechazadas: int


class TotalesRechazos(BaseModel):
    verificados: int
    rechazados: int
    finalizados: int
    porcentaje_rechazo: Decimal | None
    unidades_rechazadas: int


class FilaMotivo(BaseModel):
    destino_codigo: str
    destino_nombre: str
    motivo: str
    bultos: int
    unidades: int


class ReporteRechazos(ReporteBase):
    filas: list[FilaRechazos]
    totales: TotalesRechazos
    motivos: list[FilaMotivo]
