// Cliente HTTP tipado. Todas las reglas y cálculos están en el backend:
// este módulo sólo envía solicitudes y convierte las respuestas de error.

import type {
  Bulto, BultoResumen, CodigoMedio, Cotizacion, DetalleError, Devolucion, Existencia, Ingreso, ItemVenta,
  MedioPago, NombreReporte, Orden, OrdenResumen, Producto, Proveedor, Reporte, ResultadoImportacion, Sucursal,
  TipoImportacion, Venta, VentaResumen,
} from "./tipos"

/** El servidor respondió con un error (422 dato inválido, 404 inexistente, 409 conflicto). */
export class ErrorApi extends Error {
  readonly estado: number
  readonly codigo: string
  readonly detalles: DetalleError[]

  constructor(estado: number, codigo: string, mensaje: string, detalles: DetalleError[]) {
    super(mensaje)
    this.estado = estado
    this.codigo = codigo
    this.detalles = detalles
  }
}

/** No hubo respuesta: la operación PUDO haberse registrado. Nunca se interpreta como confirmada ni como fallida. */
export class ErrorRed extends Error {
  constructor() {
    super("No se pudo comunicar con el servidor. Si estaba registrando una operación, consulte si quedó guardada antes de reintentar.")
  }
}

type Parametros = Record<string, string | number | boolean | null | undefined>

function armarRuta(ruta: string, parametros?: Parametros): string {
  const consulta = new URLSearchParams()
  for (const [clave, valor] of Object.entries(parametros ?? {})) {
    if (valor !== undefined && valor !== null && valor !== "") consulta.set(clave, String(valor))
  }
  const texto = consulta.toString()
  return `/api${ruta}${texto ? `?${texto}` : ""}`
}

async function solicitar<T>(metodo: string, ruta: string, cuerpo?: unknown, parametros?: Parametros): Promise<T> {
  const esArchivo = cuerpo instanceof FormData
  let respuesta: Response
  try {
    respuesta = await fetch(armarRuta(ruta, parametros), {
      method: metodo,
      headers: cuerpo && !esArchivo ? { "Content-Type": "application/json" } : undefined,
      body: cuerpo === undefined ? undefined : esArchivo ? cuerpo : JSON.stringify(cuerpo),
    })
  } catch {
    throw new ErrorRed()
  }
  if (!respuesta.ok) {
    let datos: { codigo?: string; mensaje?: string; detalles?: DetalleError[] } = {}
    try {
      datos = await respuesta.json()
    } catch {
      // respuesta sin cuerpo JSON (por ejemplo, el servidor de Vite sin backend)
    }
    throw new ErrorApi(respuesta.status, datos.codigo ?? "ERROR", datos.mensaje ?? `Error ${respuesta.status} del servidor`, datos.detalles ?? [])
  }
  return respuesta.json() as Promise<T>
}

const get = <T>(ruta: string, parametros?: Parametros) => solicitar<T>("GET", ruta, undefined, parametros)
const post = <T>(ruta: string, cuerpo?: unknown) => solicitar<T>("POST", ruta, cuerpo ?? {})
const put = <T>(ruta: string, cuerpo: unknown) => solicitar<T>("PUT", ruta, cuerpo)

/** URL para descargar un PDF (el navegador la abre directamente). */
export const urlPdf = (ruta: string, parametros?: Parametros) => armarRuta(ruta, parametros)

export const api = {
  // Catálogos y stock
  proveedores: () => get<Proveedor[]>("/proveedores"),
  sucursales: () => get<Sucursal[]>("/sucursales"),
  productos: () => get<Producto[]>("/productos"),
  altaCatalogo: <T>(tipo: "proveedores" | "sucursales" | "productos", datos: unknown) => post<T>(`/${tipo}`, datos),
  editarCatalogo: <T>(tipo: "proveedores" | "sucursales" | "productos", codigo: string, datos: unknown) =>
    put<T>(`/${tipo}/${encodeURIComponent(codigo)}`, datos),
  existencias: (filtros: { sucursal?: string; producto?: string }) => get<Existencia[]>("/existencias", filtros),
  configurarMinimo: (sucursal: string, producto: string, minimo: number) =>
    put<Existencia>(`/existencias/${encodeURIComponent(sucursal)}/${encodeURIComponent(producto)}/minimo`, { minimo }),
  registrarIngreso: (datos: { numero: string; producto_codigo: string; proveedor_codigo: string; cantidad: number; costo_unitario: string }) =>
    post<Ingreso>("/ingresos", datos),
  importar: (tipo: TipoImportacion, archivo: File) => {
    const formulario = new FormData()
    formulario.append("archivo", archivo)
    return post<ResultadoImportacion>(`/importaciones/${tipo}`, formulario)
  },

  // Logística
  ordenes: (pendientes: boolean) => get<OrdenResumen[]>("/ordenes", { pendientes }),
  orden: (numero: string) => get<Orden>(`/ordenes/${encodeURIComponent(numero)}`),
  crearOrden: (datos: { numero: string; necesidades: { destino_codigo: string; producto_codigo: string; cantidad: number }[] }) =>
    post<Orden>("/ordenes", datos),
  bultos: (filtros: { estado?: string; destino?: string }) => get<BultoResumen[]>("/bultos", filtros),
  bulto: (codigo: string) => get<Bulto>(`/bultos/${encodeURIComponent(codigo)}`),
  prepararBulto: (datos: { codigo: string; orden_numero: string; destino_codigo: string; remito_numero: string; lineas: { detalle_id: number; cantidad: number }[] }) =>
    post<Bulto>("/bultos", datos),
  precintar: (codigo: string, numero: string) => post<Bulto>(`/bultos/${encodeURIComponent(codigo)}/precintar`, { numero }),
  despachar: (codigo: string) => post<Bulto>(`/bultos/${encodeURIComponent(codigo)}/despachar`),
  recibir: (codigo: string, intacto: boolean, motivo: string) => post<Bulto>(`/bultos/${encodeURIComponent(codigo)}/recibir`, { intacto, motivo }),
  verificar: (codigo: string, conforme: boolean, motivo: string) => post<Bulto>(`/bultos/${encodeURIComponent(codigo)}/verificar`, { conforme, motivo }),

  // Caja
  mediosPago: () => get<MedioPago[]>("/medios-pago"),
  cotizar: (datos: { local_codigo: string; medio_codigo: CodigoMedio; items: ItemVenta[] }) => post<Cotizacion>("/ventas/cotizacion", datos),
  confirmarVenta: (datos: { numero: string; local_codigo: string; medio_codigo: CodigoMedio; items: ItemVenta[]; total_esperado: string }) =>
    post<Venta>("/ventas", datos),
  ventas: (local?: string) => get<VentaResumen[]>("/ventas", { local }),
  venta: (numero: string) => get<Venta>(`/ventas/${encodeURIComponent(numero)}`),
  devolver: (datos: { numero: string; venta_numero: string; detalle_id: number; cantidad: number; apta_reventa: boolean; motivo: string }) =>
    post<Devolucion>("/devoluciones", datos),

  // Reportes
  reporte: (nombre: NombreReporte, filtros: Parametros) => get<Reporte>(`/reportes/${nombre}`, filtros),
}

/** Error legible para mostrar en pantalla. */
export function describirError(error: unknown): { mensaje: string; detalles: DetalleError[] } {
  if (error instanceof ErrorApi) return { mensaje: error.message, detalles: error.detalles }
  if (error instanceof ErrorRed) return { mensaje: error.message, detalles: [] }
  return { mensaje: "Ocurrió un error inesperado en la interfaz.", detalles: [] }
}
