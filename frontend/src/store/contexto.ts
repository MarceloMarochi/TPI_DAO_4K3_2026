// Contexto compartido: el borrador y la confirmación sobreviven al cambio de vista.
import { create } from "zustand"
import { generarNumero } from "../lib/formato"
import { api, ErrorApi, ErrorRed } from "../lib/api"
import { coincideVenta } from "../lib/operacionVenta"
import type { SolicitudVenta } from "../lib/operacionVenta"
import type { CodigoMedio, Venta } from "../lib/tipos"

export interface ItemBorrador {
  producto_codigo: string
  producto_nombre: string
  precio: string
  cantidad: number
}

interface Borrador {
  numero: string
  medio: CodigoMedio
  items: ItemBorrador[]
  version: number
}

type EstadoConfirmacion = "enviando" | "desconocido" | "consultando" | "no_encontrada" | "diferente"
interface Operacion {
  datos: SolicitudVenta
  estado: EstadoConfirmacion
}

interface Contexto {
  localCodigo: string | null
  borrador: Borrador
  operacion: Operacion | null
  confirmada: Venta | null
  errorVenta: unknown
  seleccionarLocal: (codigo: string | null) => void
  agregarItem: (item: Omit<ItemBorrador, "cantidad">) => void
  cambiarCantidad: (productoCodigo: string, cantidad: number) => void
  quitarItem: (productoCodigo: string) => void
  cambiarMedio: (medio: CodigoMedio) => void
  descartarBorrador: () => void
  confirmarVenta: (total: string, version: number) => Promise<void>
  consultarConfirmacion: () => Promise<void>
  reintentarConfirmacion: () => Promise<void>
  resolverNumeroOcupado: () => void
}

type TransporteVentas = {
  confirmarVenta: (datos: SolicitudVenta) => Promise<Venta>
  venta: (numero: string) => Promise<Venta>
}

const borradorNuevo = (): Borrador => ({ numero: generarNumero("V"), medio: "EFECTIVO", items: [], version: 0 })
const editar = (borrador: Borrador, cambios: Partial<Borrador>): Borrador => ({
  ...borrador, ...cambios, version: borrador.version + 1,
})

export function crearContexto(transporte: TransporteVentas = api) {
  return create<Contexto>()((set, get) => {
    const modificar = (cambio: (borrador: Borrador) => Borrador) => {
      if (get().operacion) return
      set({ borrador: cambio(get().borrador), errorVenta: null })
    }

    const aceptar = (datos: SolicitudVenta, venta: Venta) => {
      if (!coincideVenta(datos, venta)) {
        set({ operacion: { datos, estado: "diferente" }, errorVenta: new ErrorApi(409, "NUMERO_OCUPADO",
          "El número pertenece a una venta con otros datos. No se confirmó este borrador.", []) })
        return
      }
      set({ confirmada: venta, operacion: null, errorVenta: null, borrador: borradorNuevo() })
    }

    const consultar = async (datos: SolicitudVenta) => {
      set({ operacion: { datos, estado: "consultando" }, errorVenta: null })
      try {
        aceptar(datos, await transporte.venta(datos.numero))
      } catch (error) {
        const estado = error instanceof ErrorApi && error.estado === 404 ? "no_encontrada" : "desconocido"
        set({ operacion: { datos, estado }, errorVenta: error })
      }
    }

    const enviar = async (datos: SolicitudVenta) => {
      set({ operacion: { datos, estado: "enviando" }, errorVenta: null, confirmada: null })
      try {
        aceptar(datos, await transporte.confirmarVenta(datos))
      } catch (error) {
        if (error instanceof ErrorApi && error.estado === 409) {
          // Puede ser el reintento de una venta ya guardada: resolver por su número.
          await consultar(datos)
          if (get().operacion?.estado === "no_encontrada") {
            set({ operacion: null, errorVenta: error, borrador: editar(get().borrador, {}) })
          }
        } else if (error instanceof ErrorApi && [400, 404, 422].includes(error.estado)) {
          set({ operacion: null, errorVenta: error, borrador: editar(get().borrador, {}) })
        } else {
          // Un 5xx o una respuesta ilegible tampoco prueban que no se haya guardado.
          set({ operacion: { datos, estado: "desconocido" }, errorVenta: error ?? new ErrorRed() })
        }
      }
    }

    return {
      localCodigo: null, borrador: borradorNuevo(), operacion: null, confirmada: null, errorVenta: null,
      seleccionarLocal: (codigo) => {
        if (!get().operacion) set({ localCodigo: codigo, borrador: borradorNuevo(), confirmada: null, errorVenta: null })
      },
      agregarItem: (item) => modificar((borrador) => {
        const existe = borrador.items.some((i) => i.producto_codigo === item.producto_codigo)
        const items = existe
          ? borrador.items.map((i) => i.producto_codigo === item.producto_codigo ? { ...i, cantidad: i.cantidad + 1 } : i)
          : [...borrador.items, { ...item, cantidad: 1 }]
        return editar(borrador, { items })
      }),
      cambiarCantidad: (productoCodigo, cantidad) => modificar((borrador) => editar(borrador, {
        items: borrador.items.map((i) => i.producto_codigo === productoCodigo ? { ...i, cantidad } : i),
      })),
      quitarItem: (productoCodigo) => modificar((borrador) => editar(borrador, {
        items: borrador.items.filter((i) => i.producto_codigo !== productoCodigo),
      })),
      cambiarMedio: (medio) => modificar((borrador) => editar(borrador, { medio })),
      descartarBorrador: () => modificar(() => borradorNuevo()),
      confirmarVenta: async (total, version) => {
        const { borrador, localCodigo, operacion } = get()
        if (operacion || !localCodigo || borrador.version !== version || !borrador.items.length) return
        const datos = Object.freeze({
          numero: borrador.numero, local_codigo: localCodigo, medio_codigo: borrador.medio,
          total_esperado: total,
          items: Object.freeze(borrador.items.map((i) => Object.freeze({ producto_codigo: i.producto_codigo, cantidad: i.cantidad }))),
        })
        await enviar(datos)
      },
      consultarConfirmacion: async () => {
        const operacion = get().operacion
        if (operacion && ["desconocido", "no_encontrada"].includes(operacion.estado)) await consultar(operacion.datos)
      },
      reintentarConfirmacion: async () => {
        const operacion = get().operacion
        if (operacion?.estado === "no_encontrada") await enviar(operacion.datos)
      },
      resolverNumeroOcupado: () => {
        // El usuario decide cambiar el número sólo tras comprobar que lo ocupa otra venta.
        if (get().operacion?.estado === "diferente") {
          set({ operacion: null, errorVenta: null,
            borrador: editar(get().borrador, { numero: generarNumero("V") }) })
        }
      },
    }
  })
}

export const useContexto = crearContexto()
