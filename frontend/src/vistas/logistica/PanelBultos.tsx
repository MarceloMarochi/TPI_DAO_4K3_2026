import { useState } from "react"
import { toast } from "sonner"

import { BadgeEstado, Campo, EstadoConsulta, MensajeError, Seccion, Seleccion, num, type Opcion } from "@/components/comunes"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { useAccion, useConsulta } from "@/hooks/useConsulta"
import { api } from "@/lib/api"
import { ETIQUETA_ACCION, ETIQUETA_ESTADO, fechaHora } from "@/lib/formato"
import type { AccionBulto, Bulto, EstadoBulto } from "@/lib/tipos"
import { cn } from "@/lib/utils"

const OPCIONES_ESTADO: Opcion[] = [
  { valor: "", etiqueta: "Todos" },
  ...(Object.entries(ETIQUETA_ESTADO) as [EstadoBulto, string][]).map(([valor, etiqueta]) => ({ valor, etiqueta })),
]

export function PanelBultos({ opcionesLocales, nombreSucursal, seleccionInicial }: {
  opcionesLocales: Opcion[]
  nombreSucursal: (codigo: string) => string
  seleccionInicial: string | null
}) {
  const [estado, setEstado] = useState("")
  const [destino, setDestino] = useState("")
  const lista = useConsulta(() => api.bultos({ estado, destino }), [estado, destino])
  const [seleccionado, setSeleccionado] = useState<string | null>(seleccionInicial)
  const detalle = useConsulta(() => (seleccionado ? api.bulto(seleccionado) : Promise.resolve(null)), [seleccionado])

  return (
    <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
      <Seccion titulo="Bultos" descripcion="Elegí un bulto para ver su contenido, su historial y las acciones disponibles.">
        <div className="mb-4 grid gap-3 sm:grid-cols-2">
          <Campo etiqueta="Estado"><Seleccion valor={estado} onCambio={setEstado} opciones={OPCIONES_ESTADO} /></Campo>
          <Campo etiqueta="Destino"><Seleccion valor={destino} onCambio={setDestino} opciones={[{ valor: "", etiqueta: "Todos" }, ...opcionesLocales]} /></Campo>
        </div>
        <EstadoConsulta cargando={lista.cargando} error={lista.error} vacio={(lista.datos ?? []).length === 0} mensajeVacio="No hay bultos con esos filtros.">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Bulto</TableHead>
                <TableHead>Destino</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className={num}>Unidades</TableHead>
                <TableHead>Último cambio</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(lista.datos ?? []).map((b) => (
                <TableRow key={b.codigo} onClick={() => setSeleccionado(b.codigo)}
                  className={cn("cursor-pointer", seleccionado === b.codigo && "bg-muted")}>
                  <TableCell className="font-medium">{b.codigo}</TableCell>
                  <TableCell>{b.destino_nombre}</TableCell>
                  <TableCell><BadgeEstado estado={b.estado} /></TableCell>
                  <TableCell className={num}>{b.unidades}</TableCell>
                  <TableCell>{fechaHora(b.fecha_ultimo_cambio)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </EstadoConsulta>
      </Seccion>

      {seleccionado ? (
        <EstadoConsulta cargando={detalle.cargando && !detalle.datos} error={detalle.error}>
          {detalle.datos && (
            <DetalleBulto bulto={detalle.datos} nombreSucursal={nombreSucursal}
              alCambiar={() => { void detalle.recargar(); void lista.recargar() }} />
          )}
        </EstadoConsulta>
      ) : (
        <Seccion titulo="Detalle del bulto"><p className="text-sm text-muted-foreground">Ningún bulto seleccionado.</p></Seccion>
      )}
    </div>
  )
}

function DetalleBulto({ bulto, nombreSucursal, alCambiar }: {
  bulto: Bulto
  nombreSucursal: (codigo: string) => string
  alCambiar: () => void
}) {
  const [accion, setAccion] = useState<AccionBulto | null>(null)

  return (
    <Seccion titulo={`Bulto ${bulto.codigo}`} descripcion={`Orden ${bulto.orden_numero} → ${nombreSucursal(bulto.destino_codigo)}`}
      acciones={<BadgeEstado estado={bulto.estado} />}>
      <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Remito</dt><dd>{bulto.remito_numero} · {bulto.estado_remito.toLowerCase()}</dd>
        <dt className="text-muted-foreground">Precinto</dt>
        <dd>{bulto.precinto_numero ?? "—"}{bulto.precinto_intacto === false && " · llegó roto"}{bulto.precinto_intacto && " · intacto"}</dd>
        <dt className="text-muted-foreground">Unidades</dt><dd>{bulto.unidades}</dd>
      </dl>

      <h3 className="mb-1 text-sm font-medium">Contenido</h3>
      <ul className="mb-4 text-sm">
        {bulto.detalles.map((d) => <li key={d.detalle_id}>{d.cantidad} × {d.producto_codigo} · {d.producto_nombre}</li>)}
      </ul>

      <h3 className="mb-2 text-sm font-medium">Historial (no se modifica)</h3>
      <ol className="mb-4 space-y-2 border-l pl-4 text-sm">
        {bulto.historial.map((c) => (
          <li key={c.secuencia} className="relative">
            <span className="absolute top-1.5 -left-[1.3rem] size-2 rounded-full bg-primary" />
            <span className="font-medium">{ETIQUETA_ESTADO[c.nuevo]}</span>{" "}
            <span className="text-muted-foreground">· {fechaHora(c.fecha)}</span>
            {c.motivo && <p className="text-muted-foreground">{c.motivo}</p>}
          </li>
        ))}
      </ol>

      {bulto.acciones_permitidas.length > 0 ? (
        <div className="flex gap-2 border-t pt-4">
          {/* Los botones salen de lo que informa el servidor: el frontend no reimplementa el patrón State. */}
          {bulto.acciones_permitidas.map((a) => (
            <Button key={a} onClick={() => setAccion(a)}>{ETIQUETA_ACCION[a]}</Button>
          ))}
        </div>
      ) : (
        <p className="border-t pt-4 text-sm text-muted-foreground">Estado final: no admite más operaciones.</p>
      )}

      {accion && (
        <DialogoAccion bulto={bulto} accion={accion} alCerrar={() => setAccion(null)}
          alCompletar={() => { setAccion(null); alCambiar() }} />
      )}
    </Seccion>
  )
}

const AYUDA: Record<AccionBulto, string> = {
  precintar: "Registrá el número del precinto de seguridad colocado en el bulto.",
  despachar: "El bulto sale del CD. El stock del CD ya se descontó al prepararlo.",
  recibir: "Controlá el precinto al llegar al local. Si está roto, el bulto se rechaza y no habilita la venta.",
  verificar: "Controlá remito y contenido. Sólo una verificación conforme suma el stock al local.",
}

function DialogoAccion({ bulto, accion, alCerrar, alCompletar }: {
  bulto: Bulto
  accion: AccionBulto
  alCerrar: () => void
  alCompletar: () => void
}) {
  const [precinto, setPrecinto] = useState("")
  const [ok, setOk] = useState(true) // precinto intacto / control conforme
  const [motivo, setMotivo] = useState("")
  const { ejecutar, pendiente, error } = useAccion()

  const confirmar = async () => {
    const operaciones: Record<AccionBulto, () => Promise<Bulto>> = {
      precintar: () => api.precintar(bulto.codigo, precinto),
      despachar: () => api.despachar(bulto.codigo),
      recibir: () => api.recibir(bulto.codigo, ok, motivo),
      verificar: () => api.verificar(bulto.codigo, ok, motivo),
    }
    const resultado = await ejecutar(operaciones[accion])
    if (resultado) {
      toast.success(`Bulto ${resultado.codigo}: ${ETIQUETA_ESTADO[resultado.estado]}`)
      alCompletar()
    }
  }

  const textos = accion === "recibir"
    ? { si: "Precinto intacto", no: "Precinto roto" }
    : { si: "Remito y contenido conformes", no: "No conforme" }

  return (
    <Dialog open onOpenChange={(abierto) => !abierto && alCerrar()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{ETIQUETA_ACCION[accion]} bulto {bulto.codigo}</DialogTitle>
          <DialogDescription>{AYUDA[accion]}</DialogDescription>
        </DialogHeader>
        <form id="form-accion" className="grid gap-3" onSubmit={(e) => { e.preventDefault(); void confirmar() }}>
          {accion === "precintar" && (
            <Campo etiqueta="Número de precinto" htmlFor="precinto"><Input id="precinto" autoFocus value={precinto} onChange={(e) => setPrecinto(e.target.value)} /></Campo>
          )}
          {(accion === "recibir" || accion === "verificar") && (
            <>
              <div className="flex gap-4 text-sm" role="radiogroup">
                {[true, false].map((valor) => (
                  <label key={String(valor)} className="flex items-center gap-2">
                    <input type="radio" name="resultado" checked={ok === valor} onChange={() => setOk(valor)} className="accent-primary" />
                    {valor ? textos.si : textos.no}
                  </label>
                ))}
              </div>
              {!ok && (
                <div className="grid gap-1.5">
                  <Label htmlFor="motivo">Motivo del rechazo (obligatorio)</Label>
                  <Textarea id="motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
                </div>
              )}
            </>
          )}
        </form>
        <MensajeError error={error} titulo="El servidor rechazó la operación" />
        <DialogFooter>
          <Button variant="outline" onClick={alCerrar}>Cancelar</Button>
          <Button type="submit" form="form-accion" disabled={pendiente} variant={ok ? "default" : "destructive"}>
            {pendiente ? "Enviando…" : ok ? ETIQUETA_ACCION[accion] : "Rechazar bulto"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
