// Formato para mostrar datos. No se usa para calcular: los importes ya vienen calculados del servidor.

import type { AccionBulto, CodigoMedio, EstadoBulto } from "./tipos"

const ZONA = "America/Argentina/Cordoba"

const formatoImporte = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" })
const formatoFechaHora = new Intl.DateTimeFormat("es-AR", { dateStyle: "short", timeStyle: "short", timeZone: ZONA })
const formatoFecha = new Intl.DateTimeFormat("es-AR", { dateStyle: "short", timeZone: ZONA })

export function importe(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "—"
  return formatoImporte.format(Number(valor))
}

export function porcentaje(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined) return "sin datos"
  return `${Number(valor).toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} %`
}

export function tasa(valor: string): string {
  return porcentaje(Number(valor) * 100)
}

export function fechaHora(iso: string): string {
  return formatoFechaHora.format(new Date(iso))
}

export function fecha(iso: string): string {
  return formatoFecha.format(new Date(iso))
}

/** Fecha de hoy en Córdoba como AAAA-MM-DD (para los filtros de reportes). */
export function hoyISO(): string {
  return new Date().toLocaleDateString("sv-SE", { timeZone: ZONA })
}

export function primerDiaDelMesISO(): string {
  return `${hoyISO().slice(0, 8)}01`
}

export const ETIQUETA_ESTADO: Record<EstadoBulto, string> = {
  PREPARADO: "Preparado",
  PRECINTADO: "Precintado",
  EN_TRANSITO: "En tránsito",
  RECIBIDO: "Recibido",
  VERIFICADO: "Verificado",
  RECHAZADO: "Rechazado",
}

export const ETIQUETA_ACCION: Record<AccionBulto, string> = {
  precintar: "Precintar",
  despachar: "Despachar",
  recibir: "Recibir",
  verificar: "Verificar",
}

export const ETIQUETA_MEDIO: Record<CodigoMedio, string> = {
  EFECTIVO: "Efectivo",
  TARJETA: "Tarjeta",
}

/**
 * Número de documento generado al iniciar el borrador (P-05 del documento maestro).
 * Se conserva hasta conocer el resultado: si la respuesta se pierde, se consulta por este número
 * en lugar de generar otro, así el reintento no crea una operación duplicada.
 */
export function generarNumero(prefijo: string): string {
  const ahora = new Date()
  const dos = (n: number) => String(n).padStart(2, "0")
  const marca = `${String(ahora.getFullYear()).slice(2)}${dos(ahora.getMonth() + 1)}${dos(ahora.getDate())}-${dos(ahora.getHours())}${dos(ahora.getMinutes())}${dos(ahora.getSeconds())}`
  const azar = Math.random().toString(36).slice(2, 4).toUpperCase()
  return `${prefijo}-${marca}-${azar}`
}
