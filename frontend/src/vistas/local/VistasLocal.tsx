import { EstadoConsulta } from "@/components/comunes"
import { useCatalogos } from "@/hooks/useCatalogos"
import { PanelExistencias } from "@/vistas/catalogos/PanelesStock"
import { PanelBultos } from "@/vistas/logistica/PanelBultos"

/** Recepción del local: recibe (control de precinto) y verifica (contenido contra remito) sus bultos. */
export function VistaRecepcion({ localCodigo }: { localCodigo: string }) {
  const catalogos = useCatalogos()
  return (
    <EstadoConsulta cargando={catalogos.cargando && !catalogos.datos} error={catalogos.error}>
      <PanelBultos key={localCodigo} ambito="local" destinoFijo={localCodigo} opcionesLocales={catalogos.opcionesLocales}
        nombreSucursal={catalogos.nombreSucursal} seleccionInicial={null} />
    </EstadoConsulta>
  )
}

/** Stock del local: sólo lectura. El disponible cambia por operaciones y los mínimos los define el CD. */
export function VistaStockLocal({ localCodigo }: { localCodigo: string }) {
  const catalogos = useCatalogos()
  return (
    <EstadoConsulta cargando={catalogos.cargando && !catalogos.datos} error={catalogos.error}>
      <PanelExistencias key={localCodigo} sucursalFija={localCodigo} minimoEditable={false}
        opcionesSucursales={catalogos.opcionesSucursales} opcionesProductos={catalogos.opcionesProductos} />
    </EstadoConsulta>
  )
}
