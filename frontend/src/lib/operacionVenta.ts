import type { CodigoMedio, Venta } from "./tipos"

/** Copia de la solicitud enviada; no depende de un formulario que pueda desmontarse. */
export interface SolicitudVenta {
  readonly numero: string
  readonly local_codigo: string
  readonly medio_codigo: CodigoMedio
  readonly items: ReadonlyArray<{ readonly producto_codigo: string; readonly cantidad: number }>
  readonly total_esperado: string
}

function centavos(texto: string): bigint | null {
  if (!/^\d+(\.\d{1,2})?$/.test(texto)) return null
  const [entero, decimal = ""] = texto.split(".")
  return BigInt(entero) * 100n + BigInt(decimal.padEnd(2, "0"))
}

export function coincideVenta(datos: SolicitudVenta, venta: Venta): boolean {
  const cantidades = new Map<string, number>()
  for (const item of datos.items) {
    cantidades.set(item.producto_codigo, (cantidades.get(item.producto_codigo) ?? 0) + item.cantidad)
  }
  const importe = centavos(datos.total_esperado)
  return venta.numero === datos.numero && venta.local_codigo === datos.local_codigo
    && venta.medio_codigo === datos.medio_codigo && importe !== null
    && centavos(venta.total_cobrado) === importe
    && venta.lineas.length === cantidades.size
    && new Set(venta.lineas.map((l) => l.producto_codigo)).size === cantidades.size
    && venta.lineas.every((l) => cantidades.get(l.producto_codigo) === l.cantidad)
}
