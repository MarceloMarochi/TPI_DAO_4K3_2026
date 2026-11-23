import { useEffect, useMemo } from "react"

import type { Opcion } from "@/components/comunes"
import { api } from "@/lib/api"
import { useConsulta } from "./useConsulta"

const EVENTO_CAMBIO = "catalogos:cambio"

/** Avisa a todas las vistas que usan catálogos (por ejemplo, el selector del encabezado) que vuelvan a cargarlos. */
export function avisarCambioDeCatalogos() {
  window.dispatchEvent(new Event(EVENTO_CAMBIO))
}

/** Productos, establecimientos y proveedores, con opciones listas para los selectores. */
export function useCatalogos() {
  const consulta = useConsulta(async () => {
    const [productos, sucursales, proveedores] = await Promise.all([api.productos(), api.sucursales(), api.proveedores()])
    return { productos, sucursales, proveedores }
  })
  const { recargar } = consulta
  useEffect(() => {
    const alCambiar = () => void recargar()
    window.addEventListener(EVENTO_CAMBIO, alCambiar)
    return () => window.removeEventListener(EVENTO_CAMBIO, alCambiar)
  }, [recargar])

  const derivados = useMemo(() => {
    const productos = consulta.datos?.productos ?? []
    const sucursales = consulta.datos?.sucursales ?? []
    const proveedores = consulta.datos?.proveedores ?? []
    const locales = sucursales.filter((s) => !s.es_cd)
    return {
      productos,
      sucursales,
      proveedores,
      locales,
      cd: sucursales.find((s) => s.es_cd) ?? null,
      opcionesProductos: productos.map<Opcion>((p) => ({ valor: p.codigo, etiqueta: `${p.codigo} · ${p.nombre}` })),
      opcionesLocales: locales.map<Opcion>((s) => ({ valor: s.codigo, etiqueta: s.nombre })),
      opcionesSucursales: sucursales.map<Opcion>((s) => ({ valor: s.codigo, etiqueta: s.es_cd ? `${s.nombre} (CD)` : s.nombre })),
      opcionesProveedores: proveedores.map<Opcion>((p) => ({ valor: p.codigo, etiqueta: `${p.codigo} · ${p.nombre}` })),
      nombreSucursal: (codigo: string) => sucursales.find((s) => s.codigo === codigo)?.nombre ?? codigo,
    }
  }, [consulta.datos])

  return { ...consulta, ...derivados }
}
