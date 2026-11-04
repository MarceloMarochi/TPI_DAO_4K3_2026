import { useMemo, useState } from "react"
import { PackagePlusIcon, PlusIcon, Trash2Icon } from "lucide-react"
import { toast } from "sonner"

import { Campo, EstadoConsulta, MensajeError, Seccion, Seleccion, num, type Opcion } from "@/components/comunes"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAccion, useConsulta } from "@/hooks/useConsulta"
import { api } from "@/lib/api"
import { fechaHora, generarNumero } from "@/lib/formato"
import type { Bulto, Orden } from "@/lib/tipos"
import { cn } from "@/lib/utils"

interface Linea {
  destino_codigo: string
  producto_codigo: string
  cantidad: string
}

const lineaVacia = (): Linea => ({ destino_codigo: "", producto_codigo: "", cantidad: "" })

export function PanelOrdenes({ opcionesLocales, opcionesProductos, nombreSucursal, alPrepararBulto }: {
  opcionesLocales: Opcion[]
  opcionesProductos: Opcion[]
  nombreSucursal: (codigo: string) => string
  alPrepararBulto: (bulto: Bulto) => void
}) {
  const [soloPendientes, setSoloPendientes] = useState(true)
  const ordenes = useConsulta(() => api.ordenes(soloPendientes), [soloPendientes])
  const [seleccionada, setSeleccionada] = useState<string | null>(null)
  const detalle = useConsulta(() => (seleccionada ? api.orden(seleccionada) : Promise.resolve(null)), [seleccionada])

  const refrescar = () => {
    void ordenes.recargar()
    void detalle.recargar()
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-6">
        <NuevaOrden opcionesLocales={opcionesLocales} opcionesProductos={opcionesProductos}
          alCrear={(orden) => { setSeleccionada(orden.numero); refrescar() }} />

        <Seccion titulo="Órdenes de reposición" acciones={
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={soloPendientes} onCheckedChange={setSoloPendientes} /> Sólo con pendientes
          </label>
        }>
          <EstadoConsulta cargando={ordenes.cargando} error={ordenes.error} vacio={(ordenes.datos ?? []).length === 0}
            mensajeVacio="No hay órdenes con unidades pendientes de preparar.">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Orden</TableHead>
                  <TableHead>Fecha</TableHead>
                  <TableHead className={num}>Solicitado</TableHead>
                  <TableHead className={num}>Pendiente</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(ordenes.datos ?? []).map((o) => (
                  <TableRow key={o.numero} onClick={() => setSeleccionada(o.numero)}
                    className={cn("cursor-pointer", seleccionada === o.numero && "bg-muted")}>
                    <TableCell className="font-medium">{o.numero}</TableCell>
                    <TableCell>{fechaHora(o.fecha)}</TableCell>
                    <TableCell className={num}>{o.solicitado}</TableCell>
                    <TableCell className={num}>{o.pendiente > 0 ? o.pendiente : <Badge variant="secondary">Completa</Badge>}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </EstadoConsulta>
        </Seccion>
      </div>

      {seleccionada ? (
        <EstadoConsulta cargando={detalle.cargando && !detalle.datos} error={detalle.error}>
          {detalle.datos && (
            <PrepararBulto key={detalle.datos.numero + detalle.datos.detalles.map((d) => d.asignado).join()}
              orden={detalle.datos} nombreSucursal={nombreSucursal}
              alPreparar={(bulto) => { refrescar(); alPrepararBulto(bulto) }} />
          )}
        </EstadoConsulta>
      ) : (
        <Seccion titulo="Preparar bulto">
          <p className="text-sm text-muted-foreground">Elegí una orden para ver sus líneas y preparar un bulto.</p>
        </Seccion>
      )}
    </div>
  )
}

/** Consolida necesidades de los locales: si se repite producto y destino, el servidor suma las cantidades. */
function NuevaOrden({ opcionesLocales, opcionesProductos, alCrear }: {
  opcionesLocales: Opcion[]
  opcionesProductos: Opcion[]
  alCrear: (orden: Orden) => void
}) {
  const [numero, setNumero] = useState(() => generarNumero("O"))
  const [lineas, setLineas] = useState<Linea[]>([lineaVacia()])
  const { ejecutar, pendiente, error } = useAccion()

  const cambiar = (indice: number, cambios: Partial<Linea>) =>
    setLineas(lineas.map((l, i) => (i === indice ? { ...l, ...cambios } : l)))

  const crear = async () => {
    const orden = await ejecutar(() => api.crearOrden({
      numero,
      necesidades: lineas.map((l) => ({ ...l, cantidad: Number(l.cantidad) })),
    }))
    if (orden) {
      toast.success(`Orden ${orden.numero} creada con ${orden.detalles.length} línea(s)`)
      setNumero(generarNumero("O"))
      setLineas([lineaVacia()])
      alCrear(orden)
    }
  }

  const completa = lineas.every((l) => l.destino_codigo && l.producto_codigo && l.cantidad)

  return (
    <Seccion titulo="Nueva orden de reposición" descripcion="Origen: Centro de Distribución. Cada línea indica local destino, producto y cantidad.">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); void crear() }}>
        <Campo etiqueta="Número de orden" htmlFor="orden-numero" className="max-w-xs">
          <Input id="orden-numero" value={numero} onChange={(e) => setNumero(e.target.value)} />
        </Campo>
        {lineas.map((linea, i) => (
          <div key={i} className="grid grid-cols-[1fr_1.5fr_5rem_auto] items-end gap-2">
            <Campo etiqueta={i === 0 ? "Destino" : ""}>
              <Seleccion valor={linea.destino_codigo} onCambio={(v) => cambiar(i, { destino_codigo: v })} opciones={opcionesLocales} />
            </Campo>
            <Campo etiqueta={i === 0 ? "Producto" : ""}>
              <Seleccion valor={linea.producto_codigo} onCambio={(v) => cambiar(i, { producto_codigo: v })} opciones={opcionesProductos} />
            </Campo>
            <Campo etiqueta={i === 0 ? "Cantidad" : ""}>
              <Input inputMode="numeric" value={linea.cantidad} onChange={(e) => cambiar(i, { cantidad: e.target.value })} aria-label="Cantidad" />
            </Campo>
            <Button type="button" variant="ghost" size="icon" aria-label="Quitar línea" disabled={lineas.length === 1}
              onClick={() => setLineas(lineas.filter((_, j) => j !== i))}>
              <Trash2Icon />
            </Button>
          </div>
        ))}
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={() => setLineas([...lineas, lineaVacia()])}>
            <PlusIcon data-icon="inline-start" /> Agregar línea
          </Button>
          <Button type="submit" disabled={pendiente || !completa}>{pendiente ? "Creando…" : "Crear orden"}</Button>
        </div>
        <MensajeError error={error} titulo="No se creó la orden" />
      </form>
    </Seccion>
  )
}

/** Arma un bulto para UN destino con líneas de la orden. Al guardarlo se descuenta el CD y el contenido queda fijo. */
function PrepararBulto({ orden, nombreSucursal, alPreparar }: {
  orden: Orden
  nombreSucursal: (codigo: string) => string
  alPreparar: (bulto: Bulto) => void
}) {
  const destinos = useMemo(
    () => [...new Set(orden.detalles.filter((d) => d.pendiente > 0).map((d) => d.destino_codigo))],
    [orden])
  const [destino, setDestino] = useState(destinos[0] ?? "")
  const [codigo, setCodigo] = useState(() => generarNumero("B"))
  const [remito, setRemito] = useState(() => generarNumero("R"))
  const [cantidades, setCantidades] = useState<Record<number, string>>(
    () => Object.fromEntries(orden.detalles.map((d) => [d.id, String(d.pendiente)])))
  const { ejecutar, pendiente, error } = useAccion()

  const lineasDestino = orden.detalles.filter((d) => d.destino_codigo === destino)

  const preparar = async () => {
    const lineas = lineasDestino
      .map((d) => ({ detalle_id: d.id, cantidad: Number(cantidades[d.id] || 0) }))
      .filter((l) => l.cantidad > 0)
    const bulto = await ejecutar(() => api.prepararBulto({ codigo, orden_numero: orden.numero, destino_codigo: destino, remito_numero: remito, lineas }))
    if (bulto) {
      toast.success(`Bulto ${bulto.codigo} preparado con ${bulto.unidades} unidades`)
      alPreparar(bulto)
    }
  }

  return (
    <Seccion titulo={`Orden ${orden.numero}`} descripcion={orden.cerrada ? "En preparación: las necesidades ya no se modifican." : "Abierta: todavía no tiene bultos."}>
      <Table className="mb-4">
        <TableHeader>
          <TableRow>
            <TableHead>Destino</TableHead>
            <TableHead>Producto</TableHead>
            <TableHead className={num}>Solicitado</TableHead>
            <TableHead className={num}>En bultos</TableHead>
            <TableHead className={num}>Pendiente</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {orden.detalles.map((d) => (
            <TableRow key={d.id}>
              <TableCell>{nombreSucursal(d.destino_codigo)}</TableCell>
              <TableCell>{d.producto_codigo} · {d.producto_nombre}</TableCell>
              <TableCell className={num}>{d.solicitado}</TableCell>
              <TableCell className={num}>{d.asignado}</TableCell>
              <TableCell className={num}>{d.pendiente}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {destinos.length === 0 ? (
        <p className="text-sm text-muted-foreground">Todas las líneas de esta orden ya están en bultos.</p>
      ) : (
        <form className="space-y-3 border-t pt-4" onSubmit={(e) => { e.preventDefault(); void preparar() }}>
          <h3 className="flex items-center gap-2 font-medium"><PackagePlusIcon className="size-4" /> Preparar bulto</h3>
          <div className="grid gap-3 sm:grid-cols-3">
            <Campo etiqueta="Destino">
              <Seleccion valor={destino} onCambio={setDestino} opciones={destinos.map((d) => ({ valor: d, etiqueta: nombreSucursal(d) }))} />
            </Campo>
            <Campo etiqueta="Código de bulto" htmlFor="bulto-codigo"><Input id="bulto-codigo" value={codigo} onChange={(e) => setCodigo(e.target.value)} /></Campo>
            <Campo etiqueta="Número de remito" htmlFor="bulto-remito"><Input id="bulto-remito" value={remito} onChange={(e) => setRemito(e.target.value)} /></Campo>
          </div>
          {lineasDestino.filter((d) => d.pendiente > 0).map((d) => (
            <div key={d.id} className="flex items-center justify-between gap-3 text-sm">
              <span>{d.producto_codigo} · {d.producto_nombre} <span className="text-muted-foreground">(pendiente {d.pendiente})</span></span>
              <Input className="h-7 w-24" inputMode="numeric" aria-label={`Cantidad de ${d.producto_codigo}`}
                value={cantidades[d.id] ?? ""} onChange={(e) => setCantidades({ ...cantidades, [d.id]: e.target.value })} />
            </div>
          ))}
          <Button type="submit" disabled={pendiente || !destino}>{pendiente ? "Preparando…" : "Guardar bulto preparado"}</Button>
          <MensajeError error={error} titulo="No se preparó el bulto" />
        </form>
      )}
    </Seccion>
  )
}
