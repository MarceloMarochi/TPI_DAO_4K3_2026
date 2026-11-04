// Estado compartido de la interfaz con Zustand: local seleccionado y borrador de venta.
// No es el patrón State del bulto ni una base de datos: no se persiste y se pierde al recargar.

import { create } from "zustand"
import { generarNumero } from "@/lib/formato"
import type { CodigoMedio } from "@/lib/tipos"

export interface ItemBorrador {
  producto_codigo: string
  producto_nombre: string
  precio: string // sólo para mostrar; el total lo calcula el servidor
  cantidad: number
}

interface Borrador {
  numero: string
  medio: CodigoMedio
  items: ItemBorrador[]
  version: number // cambia con cada edición: invalida la cotización anterior
}

interface Contexto {
  localCodigo: string | null
  borrador: Borrador
  seleccionarLocal: (codigo: string | null) => void
  agregarItem: (item: Omit<ItemBorrador, "cantidad">) => void
  cambiarCantidad: (productoCodigo: string, cantidad: number) => void
  quitarItem: (productoCodigo: string) => void
  cambiarMedio: (medio: CodigoMedio) => void
  descartarBorrador: () => void
}

const borradorNuevo = (): Borrador => ({ numero: generarNumero("V"), medio: "EFECTIVO", items: [], version: 0 })

const editar = (borrador: Borrador, cambios: Partial<Borrador>): Borrador => ({
  ...borrador,
  ...cambios,
  version: borrador.version + 1,
})

export const useContexto = create<Contexto>()((set) => ({
  localCodigo: null,
  borrador: borradorNuevo(),

  // Al cambiar de local se descarta el borrador para no mezclar existencias de establecimientos distintos.
  seleccionarLocal: (codigo) => set({ localCodigo: codigo, borrador: borradorNuevo() }),

  agregarItem: (item) =>
    set(({ borrador }) => {
      const existente = borrador.items.find((i) => i.producto_codigo === item.producto_codigo)
      const items = existente
        ? borrador.items.map((i) => (i === existente ? { ...i, cantidad: i.cantidad + 1 } : i))
        : [...borrador.items, { ...item, cantidad: 1 }]
      return { borrador: editar(borrador, { items }) }
    }),

  cambiarCantidad: (productoCodigo, cantidad) =>
    set(({ borrador }) => ({
      borrador: editar(borrador, {
        items: borrador.items.map((i) => (i.producto_codigo === productoCodigo ? { ...i, cantidad } : i)),
      }),
    })),

  quitarItem: (productoCodigo) =>
    set(({ borrador }) => ({
      borrador: editar(borrador, { items: borrador.items.filter((i) => i.producto_codigo !== productoCodigo) }),
    })),

  cambiarMedio: (medio) => set(({ borrador }) => ({ borrador: editar(borrador, { medio }) })),

  descartarBorrador: () => set({ borrador: borradorNuevo() }),
}))
