// Tipos de los mensajes de la API (reflejan backend/app/api/esquemas.py y /openapi.json).
// Importes y tasas llegan como texto decimal ("1000.00"): el frontend sólo los muestra, nunca calcula con ellos.

export type Importe = string
export type FechaISO = string

export interface DetalleError {
  fila?: number | null
  campo?: string | null
  mensaje: string
}

// --- Catálogos ---

export interface Proveedor {
  codigo: string
  nombre: string
}

export interface Sucursal {
  codigo: string
  nombre: string
  es_cd: boolean
}

export interface Producto {
  codigo: string
  nombre: string
  categoria: string
  proveedor_codigo: string
  precio: Importe
  costo_referencia: Importe
}

export interface Existencia {
  sucursal_codigo: string
  sucursal_nombre?: string | null
  producto_codigo: string
  producto_nombre?: string | null
  disponible: number
  minimo: number
  faltante: number
}

export interface Ingreso {
  numero: string
  fecha: FechaISO
  producto_codigo: string
  proveedor_codigo: string
  cantidad: number
  costo_unitario: Importe
  importe: Importe
}

export type TipoImportacion = "proveedores" | "sucursales" | "productos" | "ingresos" | "minimos"

export interface ResultadoImportacion {
  tipo: TipoImportacion
  filas_importadas: number
}

// --- Logística ---

export type EstadoBulto = "PREPARADO" | "PRECINTADO" | "EN_TRANSITO" | "RECIBIDO" | "VERIFICADO" | "RECHAZADO"
export type AccionBulto = "precintar" | "despachar" | "recibir" | "verificar"

export interface DetalleOrden {
  id: number
  destino_codigo: string
  producto_codigo: string
  producto_nombre: string
  solicitado: number
  asignado: number
  pendiente: number
}

export interface Orden {
  numero: string
  fecha: FechaISO
  origen_codigo: string
  cerrada: boolean
  detalles: DetalleOrden[]
}

export interface OrdenResumen {
  numero: string
  fecha: FechaISO
  origen_codigo: string
  cerrada: boolean
  solicitado: number
  asignado: number
  pendiente: number
}

export interface CambioEstado {
  secuencia: number
  fecha: FechaISO
  anterior: EstadoBulto | null
  nuevo: EstadoBulto
  motivo: string
}

export interface Bulto {
  codigo: string
  orden_numero: string
  destino_codigo: string
  remito_numero: string
  precinto_numero: string | null
  precinto_intacto: boolean | null
  estado: EstadoBulto
  estado_remito: string
  acciones_permitidas: AccionBulto[]
  unidades: number
  detalles: { detalle_id: number; producto_codigo: string; producto_nombre: string; cantidad: number }[]
  historial: CambioEstado[]
}

export interface BultoResumen {
  codigo: string
  orden_numero: string
  destino_codigo: string
  destino_nombre: string
  remito_numero: string
  precinto_numero: string | null
  estado: EstadoBulto
  unidades: number
  fecha_preparacion: FechaISO
  fecha_ultimo_cambio: FechaISO
}

// --- Caja ---

export type CodigoMedio = "EFECTIVO" | "TARJETA"

export interface MedioPago {
  codigo: CodigoMedio
  tipo: "descuento" | "recargo"
  tasa: string
}

export interface ItemVenta {
  producto_codigo: string
  cantidad: number
}

export interface Cotizacion {
  local_codigo: string
  medio_codigo: CodigoMedio
  tasa: string
  lineas: { producto_codigo: string; producto_nombre: string; cantidad: number; precio_unitario: Importe; subtotal: Importe }[]
  subtotal: Importe
  ajuste: Importe
  total: Importe
}

export interface LineaVenta {
  id: number
  producto_codigo: string
  producto_nombre: string
  cantidad: number
  precio_unitario: Importe
  subtotal: Importe
  importe_cobrado: Importe
  cantidad_devuelta: number
  importe_devuelto: Importe
  cantidad_restante: number
}

export interface Venta {
  numero: string
  fecha: FechaISO
  local_codigo: string
  local_nombre: string
  medio_codigo: CodigoMedio
  tasa_aplicada: string
  subtotal: Importe
  ajuste: Importe
  total_cobrado: Importe
  comprobante_numero: string
  lineas: LineaVenta[]
}

export interface VentaResumen {
  numero: string
  fecha: FechaISO
  local_codigo: string
  local_nombre: string
  medio_codigo: CodigoMedio
  total_cobrado: Importe
  comprobante_numero: string
}

export interface Devolucion {
  numero: string
  fecha: FechaISO
  venta_numero: string
  detalle_id: number
  producto_codigo: string
  cantidad: number
  apta_reventa: boolean
  motivo: string
  importe_reintegrado: Importe
  medio_codigo: CodigoMedio
}

// --- Reportes ---

export type NombreReporte = "ventas" | "productos" | "existencias" | "rechazos"

export interface Reporte {
  reporte: NombreReporte
  titulo: string
  generado: FechaISO
  filtros: Record<string, string | boolean>
  filas: Record<string, string | number | boolean | null>[]
  totales: Record<string, string | number | null>
  grafico?: { local_codigo: string; local_nombre: string; neto: Importe }[]
  motivos?: { destino_codigo: string; destino_nombre: string; motivo: string; bultos: number; unidades: number }[]
}
