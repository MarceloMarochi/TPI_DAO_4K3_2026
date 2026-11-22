import { useState } from "react"
import { MapPinIcon, StoreIcon, WarehouseIcon } from "lucide-react"

import { Seleccion } from "@/components/comunes"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { avisarCambioDeCatalogos, useCatalogos } from "@/hooks/useCatalogos"
import { useContexto } from "@/store/contexto"
import { ImportarCSV } from "@/vistas/catalogos/PanelesStock"

/** Cambia el establecimiento en el que se opera. Contexto operativo, no un control de permisos. */
function useCambioDeEstablecimiento() {
  const sucursalCodigo = useContexto((s) => s.sucursalCodigo)
  const bloqueado = useContexto((s) => s.operacion !== null)
  const hayBorrador = useContexto((s) => s.borrador.items.length > 0)
  const seleccionarSucursal = useContexto((s) => s.seleccionarSucursal)
  const [pendiente, setPendiente] = useState<string | null>(null)

  const cambiar = (codigo: string) => {
    if (bloqueado || codigo === (sucursalCodigo ?? "")) return
    if (hayBorrador) setPendiente(codigo)
    else seleccionarSucursal(codigo || null)
  }

  const dialogo = (
    <Dialog open={pendiente !== null} onOpenChange={(abierto) => !abierto && setPendiente(null)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>¿Descartar la venta en preparación?</DialogTitle>
          <DialogDescription>
            La venta en curso pertenece a otro local. Al cambiar de establecimiento se descarta, para no mezclar existencias.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setPendiente(null)}>Seguir con la venta</Button>
          <Button variant="destructive" disabled={bloqueado} onClick={() => { seleccionarSucursal(pendiente || null); setPendiente(null) }}>
            Descartar y cambiar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )

  return { sucursalCodigo, bloqueado, cambiar, dialogo }
}

/** Selector del encabezado: "Operando en". */
export function SelectorEstablecimiento() {
  const { opcionesSucursales } = useCatalogos()
  const { sucursalCodigo, bloqueado, cambiar, dialogo } = useCambioDeEstablecimiento()

  return (
    <div className="flex items-center gap-2">
      <MapPinIcon className="size-4 text-muted-foreground" />
      <span className="text-sm font-medium">Operando en</span>
      <Seleccion disabled={bloqueado} className="w-80" valor={sucursalCodigo ?? ""} onCambio={cambiar}
        opciones={opcionesSucursales} placeholder="Elegir establecimiento" />
      {dialogo}
    </div>
  )
}

/** Pantalla inicial: antes de operar hay que decir dónde se está. */
export function ElegirEstablecimiento() {
  const { cd, locales } = useCatalogos()
  const { cambiar } = useCambioDeEstablecimiento()

  return (
    <Card className="mx-auto max-w-2xl">
      <CardHeader>
        <CardTitle>¿Dónde estás operando?</CardTitle>
        <CardDescription>
          El Centro de Distribución administra catálogos, ingresa mercadería, arma órdenes y despacha bultos.
          Cada local recibe y verifica sus bultos, vende y registra devoluciones.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        {cd && (
          <Button variant="outline" className="h-auto justify-start gap-3 py-3 sm:col-span-2" onClick={() => cambiar(cd.codigo)}>
            <WarehouseIcon /> <span className="text-left"><strong>{cd.nombre}</strong><br /><span className="text-xs text-muted-foreground">Centro de Distribución</span></span>
          </Button>
        )}
        {locales.map((local) => (
          <Button key={local.codigo} variant="outline" className="h-auto justify-start gap-3 py-3" onClick={() => cambiar(local.codigo)}>
            <StoreIcon /> <span className="text-left"><strong>{local.nombre}</strong><br /><span className="text-xs text-muted-foreground">Local {local.codigo}</span></span>
          </Button>
        ))}
        {!cd && locales.length === 0 && (
          // Base vacía: sin establecimientos no hay dónde operar, así que se permite importarlos acá.
          <div className="space-y-3 sm:col-span-2">
            <p className="text-sm text-muted-foreground">Todavía no hay establecimientos. Importalos desde un CSV (o cargá los datos de ejemplo con <code>python -m app.inicializar --demo</code>).</p>
            <ImportarCSV alImportar={avisarCambioDeCatalogos} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
