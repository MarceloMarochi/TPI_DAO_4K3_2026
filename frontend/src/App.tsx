import { useEffect, useState } from "react"
import { BarChart3Icon, BoxesIcon, ShoppingCartIcon, StoreIcon, TruckIcon } from "lucide-react"

import { Seleccion } from "@/components/comunes"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Toaster } from "@/components/ui/sonner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCatalogos } from "@/hooks/useCatalogos"
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
          <SelectorLocal />
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

/** Local en el que se opera la caja. Es contexto operativo, no un control de permisos. */
function SelectorLocal() {
  const { opcionesLocales } = useCatalogos()
  const localCodigo = useContexto((s) => s.localCodigo)
  const bloqueado = useContexto((s) => s.operacion !== null)
  const hayBorrador = useContexto((s) => s.borrador.items.length > 0)
  const seleccionarLocal = useContexto((s) => s.seleccionarLocal)
  const [pendiente, setPendiente] = useState<string | null>(null)

  const cambiar = (codigo: string) => {
    if (bloqueado || codigo === (localCodigo ?? "")) return
    if (hayBorrador) setPendiente(codigo)
    else seleccionarLocal(codigo || null)
  }

  return (
    <div className="flex items-center gap-2">
      <StoreIcon className="size-4 text-muted-foreground" />
      <Seleccion disabled={bloqueado} className="w-56" valor={localCodigo ?? ""} onCambio={cambiar} opciones={opcionesLocales} placeholder="Elegir local de caja" />
      <Dialog open={pendiente !== null} onOpenChange={(abierto) => !abierto && setPendiente(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>¿Descartar la venta en preparación?</DialogTitle>
            <DialogDescription>
              La venta en curso pertenece a otro local. Al cambiar de local se descarta, para no mezclar existencias de establecimientos distintos.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendiente(null)}>Seguir con la venta</Button>
            <Button variant="destructive" disabled={bloqueado} onClick={() => { seleccionarLocal(pendiente || null); setPendiente(null) }}>Descartar y cambiar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
