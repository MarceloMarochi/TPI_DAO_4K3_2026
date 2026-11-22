import { useEffect, useState } from "react"
import { BarChart3Icon, BoxesIcon, PackageCheckIcon, ShoppingCartIcon, TruckIcon, WarehouseIcon, type LucideIcon } from "lucide-react"

import { EstadoConsulta } from "@/components/comunes"
import { Toaster } from "@/components/ui/sonner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCatalogos } from "@/hooks/useCatalogos"
import { AREAS_DEL_AMBITO, ambitoDe, type Area } from "@/lib/contextoOperativo"
import { useContexto } from "@/store/contexto"
import { VistaCaja } from "@/vistas/caja/VistaCaja"
import { VistaCatalogos } from "@/vistas/catalogos/VistaCatalogos"
import { VistaRecepcion, VistaStockLocal } from "@/vistas/local/VistasLocal"
import { VistaLogistica } from "@/vistas/logistica/VistaLogistica"
import { VistaReportes } from "@/vistas/reportes/VistaReportes"
import { ElegirEstablecimiento, SelectorEstablecimiento } from "@/vistas/SelectorEstablecimiento"

const AREAS: Record<Area, { etiqueta: string; icono: LucideIcon }> = {
  catalogos: { etiqueta: "Catálogos y stock", icono: BoxesIcon },
  logistica: { etiqueta: "Logística", icono: TruckIcon },
  reportes: { etiqueta: "Reportes", icono: BarChart3Icon },
  recepcion: { etiqueta: "Recepción", icono: PackageCheckIcon },
  caja: { etiqueta: "Caja", icono: ShoppingCartIcon },
  stock: { etiqueta: "Stock del local", icono: WarehouseIcon },
}

export default function App() {
  const catalogos = useCatalogos()
  const sucursalCodigo = useContexto((s) => s.sucursalCodigo)
  const confirmacionPendiente = useContexto((s) => s.operacion !== null)
  useEffect(() => {
    if (!confirmacionPendiente) return
    const avisar = (evento: BeforeUnloadEvent) => { evento.preventDefault(); evento.returnValue = "" }
    window.addEventListener("beforeunload", avisar)
    return () => window.removeEventListener("beforeunload", avisar)
  }, [confirmacionPendiente])

  // Cada lugar ve sólo lo propio: el CD administra y despacha; el local recibe, vende y consulta su stock.
  const sucursal = catalogos.sucursales.find((s) => s.codigo === sucursalCodigo) ?? null
  const ambito = sucursal ? ambitoDe(sucursal.es_cd) : null
  const areas = ambito ? AREAS_DEL_AMBITO[ambito] : []
  const [elegida, setArea] = useState<Area | null>(null)
  const area = elegida && areas.includes(elegida) ? elegida : areas[0]

  return (
    <div className="min-h-svh bg-muted/40">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div>
            <h1 className="text-lg font-semibold">Ventas e Inventario</h1>
            <p className="text-xs text-muted-foreground">Centro de Distribución a Locales · Grupo G-029</p>
          </div>
          {sucursal && <SelectorEstablecimiento />}
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <EstadoConsulta cargando={catalogos.cargando && !catalogos.datos} error={catalogos.error}>
          {!sucursal || !area ? (
            <ElegirEstablecimiento />
          ) : (
            <Tabs value={area} onValueChange={(v) => setArea(v as Area)}>
              <TabsList className="mb-6 h-10 w-full sm:w-fit">
                {areas.map((valor) => {
                  const { etiqueta, icono: Icono } = AREAS[valor]
                  return (
                    <TabsTrigger key={valor} value={valor} className="px-3">
                      <Icono /> <span className="hidden sm:inline">{etiqueta}</span>
                    </TabsTrigger>
                  )
                })}
              </TabsList>
              {area === "catalogos" && <TabsContent value="catalogos"><VistaCatalogos /></TabsContent>}
              {area === "logistica" && <TabsContent value="logistica"><VistaLogistica /></TabsContent>}
              {area === "reportes" && <TabsContent value="reportes"><VistaReportes /></TabsContent>}
              {area === "recepcion" && <TabsContent value="recepcion"><VistaRecepcion localCodigo={sucursal.codigo} /></TabsContent>}
              {area === "caja" && <TabsContent value="caja"><VistaCaja /></TabsContent>}
              {area === "stock" && <TabsContent value="stock"><VistaStockLocal localCodigo={sucursal.codigo} /></TabsContent>}
            </Tabs>
          )}
        </EstadoConsulta>
      </main>
      <Toaster richColors position="top-right" />
    </div>
  )
}
