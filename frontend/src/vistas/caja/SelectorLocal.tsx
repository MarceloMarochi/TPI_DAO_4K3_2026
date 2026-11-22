import { useState } from "react"
import { StoreIcon } from "lucide-react"

import { Seleccion } from "@/components/comunes"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { useCatalogos } from "@/hooks/useCatalogos"
import { useContexto } from "@/store/contexto"

/** Local en el que se opera la caja. Es contexto operativo, no un control de permisos. */
export function SelectorLocal() {
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
      <span className="text-sm font-medium">Local de caja</span>
      <Seleccion disabled={bloqueado} className="w-56" valor={localCodigo ?? ""} onCambio={cambiar} opciones={opcionesLocales} placeholder="Elegir local" />
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
