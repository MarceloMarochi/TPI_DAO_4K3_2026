import { useEffect, useState } from "react"
import { BarChart3Icon, BoxesIcon, ShoppingCartIcon, TruckIcon } from "lucide-react"

import { Toaster } from "@/components/ui/sonner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useContexto } from "@/store/contexto"
import { VistaCaja } from "@/vistas/caja/VistaCaja"
import { VistaCatalogos } from "@/vistas/catalogos/VistaCatalogos"
import { VistaLogistica } from "@/vistas/logistica/VistaLogistica"
import { VistaReportes } from "@/vistas/reportes/VistaReportes"

const AREAS = [
  { valor: "catalogos", etiqueta: "Catálogos y stock", icono: BoxesIcon },
  { valor: "logistica", etiqueta: "Logística", icono: TruckIcon },
  { valor: "caja", etiqueta: "Caja", icono: ShoppingCartIcon },
  { valor: "reportes", etiqueta: "Reportes", icono: BarChart3Icon },
] as const

export default function App() {
  const [area, setArea] = useState<string>("catalogos")
  const confirmacionPendiente = useContexto((s) => s.operacion !== null)
  useEffect(() => {
    if (!confirmacionPendiente) return
    const avisar = (evento: BeforeUnloadEvent) => { evento.preventDefault(); evento.returnValue = "" }
    window.addEventListener("beforeunload", avisar)
    return () => window.removeEventListener("beforeunload", avisar)
  }, [confirmacionPendiente])

  return (
    <div className="min-h-svh bg-muted/40">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div>
            <h1 className="text-lg font-semibold">Ventas e Inventario</h1>
            <p className="text-xs text-muted-foreground">Centro de Distribución a Locales · Grupo G-029</p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <Tabs value={area} onValueChange={(v) => setArea(String(v))}>
          <TabsList className="mb-6 h-10 w-full sm:w-fit">
            {AREAS.map(({ valor, etiqueta, icono: Icono }) => (
              <TabsTrigger key={valor} value={valor} className="px-3">
                <Icono /> <span className="hidden sm:inline">{etiqueta}</span>
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value="catalogos"><VistaCatalogos /></TabsContent>
          <TabsContent value="logistica"><VistaLogistica /></TabsContent>
          <TabsContent value="caja"><VistaCaja /></TabsContent>
          <TabsContent value="reportes"><VistaReportes /></TabsContent>
        </Tabs>
      </main>
      <Toaster richColors position="top-right" />
    </div>
  )
}
