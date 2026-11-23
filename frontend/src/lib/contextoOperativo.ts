/**
 * Contexto operativo: dónde está parado quien usa el sistema (el CD o un local).
 *
 * Es una ayuda de interfaz, NO un control de seguridad: no hay usuarios ni autenticación
 * (fuera de alcance), así que el backend no sabe quién llama. Sólo ordena la pantalla
 * para que cada lugar vea y haga lo propio.
 *
 * Tampoco reemplaza al patrón State: el servidor sigue decidiendo qué acciones admite
 * el bulto según su estado (`acciones_permitidas`). El contexto sólo decide cuáles de
 * esas acciones se ofrecen en este lugar.
 */
import type { AccionBulto, EstadoBulto } from "./tipos"

export type Ambito = "cd" | "local"

export type Area = "catalogos" | "logistica" | "reportes" | "recepcion" | "caja" | "stock"

/** Áreas visibles en cada lugar, en el orden en que se muestran. */
export const AREAS_DEL_AMBITO: Record<Ambito, Area[]> = {
  cd: ["catalogos", "logistica", "reportes"],
  local: ["recepcion", "caja", "stock"],
}

/** Quién ejecuta cada paso del circuito físico del bulto. */
export const ACCIONES_DEL_AMBITO: Record<Ambito, AccionBulto[]> = {
  cd: ["precintar", "despachar"],
  local: ["recibir", "verificar"],
}

/** Un local ve los bultos desde que salen del CD; antes siguen siendo asunto del CD. */
export const ESTADOS_VISIBLES_EN_LOCAL: EstadoBulto[] = ["EN_TRANSITO", "RECIBIDO", "VERIFICADO", "RECHAZADO"]

export function ambitoDe(esCd: boolean): Ambito {
  return esCd ? "cd" : "local"
}

/** De las acciones que el estado del bulto permite, las que se hacen en este lugar. */
export function accionesEnAmbito(permitidas: AccionBulto[], ambito: Ambito): AccionBulto[] {
  return permitidas.filter((accion) => ACCIONES_DEL_AMBITO[ambito].includes(accion))
}

/** Si el bulto espera una acción que corresponde al otro lugar, indica cuál y dónde. */
export function accionPendienteEnOtroLugar(permitidas: AccionBulto[], ambito: Ambito): { accion: AccionBulto; lugar: Ambito } | null {
  const otro: Ambito = ambito === "cd" ? "local" : "cd"
  const accion = permitidas.find((a) => ACCIONES_DEL_AMBITO[otro].includes(a))
  return accion ? { accion, lugar: otro } : null
}
