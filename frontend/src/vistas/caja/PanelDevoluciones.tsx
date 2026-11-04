import { useState } from "react"
import { toast } from "sonner"

import { Campo, EstadoConsulta, MensajeError, Seccion, num } from "@/components/comunes"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { useAccion, useConsulta } from "@/hooks/useConsulta"
import { api } from "@/lib/api"
import { ETIQUETA_MEDIO, fechaHora, generarNumero, importe } from "@/lib/formato"
import type { Devolucion, LineaVenta, Venta } from "@/lib/tipos"
import { cn } from "@/lib/utils"

/** Devolución de UNA línea de una venta registrada. El reintegro lo calcula el servidor sobre lo cobrado. */
export function PanelDevoluciones({ localCodigo }: { localCodigo: string }) {
  const recientes = useConsulta(() => api.ventas(localCodigo), [localCodigo])
  const [numeroBuscado, setNumeroBuscado] = useState("")
  const [venta, setVenta] = useState<Venta | null>(null)
  const buscar = useAccion()

  const abrir = async (numero: string) => {
    const encontrada = await buscar.ejecutar(() => api.venta(numero.trim()))
    setVenta(encontrada ?? null)
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_3fr]">
      <Seccion titulo="Buscar venta">
        <form className="mb-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); void abrir(numeroBuscado) }}>
          <Input placeholder="Número de venta" value={numeroBuscado} onChange={(e) => setNumeroBuscado(e.target.value)} />
          <Button type="submit" disabled={!numeroBuscado.trim() || buscar.pendiente}>Buscar</Button>
        </form>
        <MensajeError error={buscar.error} titulo="No se encontró la venta" />
        <h3 className="mt-2 mb-1 text-sm font-medium">Últimas ventas de este local</h3>
        <EstadoConsulta cargando={recientes.cargando} error={recientes.error} vacio={(recientes.datos ?? []).length === 0}
          mensajeVacio="Todavía no hay ventas en este local.">
          <ul className="max-h-96 divide-y overflow-auto text-sm">
            {(recientes.datos ?? []).map((v) => (
              <li key={v.numero}>
                <button className={cn("flex w-full justify-between gap-2 px-1 py-2 text-left hover:bg-muted", venta?.numero === v.numero && "bg-muted")}
                  onClick={() => void abrir(v.numero)}>
                  <span><span className="font-medium">{v.numero}</span> · {fechaHora(v.fecha)}</span>
                  <span className="tabular-nums">{importe(v.total_cobrado)}</span>
                </button>
              </li>
            ))}
          </ul>
        </EstadoConsulta>
      </Seccion>

      {venta ? (
        <DetalleDevolucion key={venta.numero} venta={venta} alRegistrar={() => { void abrir(venta.numero); void recientes.recargar() }} />
      ) : (
        <Seccion titulo="Devolución"><p className="text-sm text-muted-foreground">Elegí una venta para devolver una de sus líneas.</p></Seccion>
      )}
    </div>
  )
}

function DetalleDevolucion({ venta, alRegistrar }: { venta: Venta; alRegistrar: () => void }) {
  const [linea, setLinea] = useState<LineaVenta | null>(null)
  const [numero, setNumero] = useState(() => generarNumero("D"))
  const [cantidad, setCantidad] = useState("1")
  const [apta, setApta] = useState(true)
  const [motivo, setMotivo] = useState("")
  const [resultado, setResultado] = useState<Devolucion | null>(null)
  const { ejecutar, pendiente, error } = useAccion()

  const registrar = async () => {
    if (!linea) return
    const devolucion = await ejecutar(() => api.devolver({
      numero, venta_numero: venta.numero, detalle_id: linea.id, cantidad: Number(cantidad), apta_reventa: apta, motivo,
    }))
    if (devolucion) {
      setResultado(devolucion)
      toast.success(`Devolución registrada: se reintegran ${importe(devolucion.importe_reintegrado)}`)
      setNumero(generarNumero("D"))
      setLinea(null)
      setMotivo("")
      alRegistrar()
    }
  }

  return (
    <Seccion titulo={`Venta ${venta.numero}`}
      descripcion={`${venta.local_nombre} · ${fechaHora(venta.fecha)} · ${ETIQUETA_MEDIO[venta.medio_codigo]} · total ${importe(venta.total_cobrado)}`}>
      <Table className="mb-4">
        <TableHeader>
          <TableRow>
            <TableHead>Producto</TableHead>
            <TableHead className={num}>Vendidas</TableHead>
            <TableHead className={num}>Devueltas</TableHead>
            <TableHead className={num}>Cobrado</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {venta.lineas.map((l) => (
            <TableRow key={l.id} className={cn(linea?.id === l.id && "bg-muted")}>
              <TableCell>{l.producto_nombre}</TableCell>
              <TableCell className={num}>{l.cantidad}</TableCell>
              <TableCell className={num}>{l.cantidad_devuelta}</TableCell>
              <TableCell className={num}>{importe(l.importe_cobrado)}</TableCell>
              <TableCell className="text-right">
                <Button size="sm" variant="outline" disabled={l.cantidad_restante === 0} onClick={() => { setLinea(l); setResultado(null) }}>
                  {l.cantidad_restante === 0 ? "Sin saldo" : "Devolver"}
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {linea && (
        <form className="grid gap-3 border-t pt-4" onSubmit={(e) => { e.preventDefault(); void registrar() }}>
          <h3 className="font-medium">Devolver {linea.producto_nombre} <span className="text-sm font-normal text-muted-foreground">(se pueden devolver {linea.cantidad_restante})</span></h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta="Número de devolución" htmlFor="dev-numero"><Input id="dev-numero" value={numero} onChange={(e) => setNumero(e.target.value)} /></Campo>
            <Campo etiqueta="Cantidad" htmlFor="dev-cantidad"><Input id="dev-cantidad" inputMode="numeric" value={cantidad} onChange={(e) => setCantidad(e.target.value)} /></Campo>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={apta} onCheckedChange={setApta} /> Mercadería inspeccionada y apta para la venta
          </label>
          <Campo etiqueta="Motivo" htmlFor="dev-motivo"><Textarea id="dev-motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} /></Campo>
          <p className="text-xs text-muted-foreground">
            El reintegro se hace por {ETIQUETA_MEDIO[venta.medio_codigo].toLowerCase()}, el medio original. {apta ? "Las unidades vuelven al disponible del local." : "Las unidades quedan fuera de venta."}
          </p>
          <div><Button type="submit" disabled={pendiente || !motivo.trim()}>{pendiente ? "Registrando…" : "Registrar devolución"}</Button></div>
        </form>
      )}
      <div className="mt-3 space-y-2">
        <MensajeError error={error} titulo="No se registró la devolución" />
        {resultado && (
          <p className="text-sm">
            Devolución <strong>{resultado.numero}</strong>: {resultado.cantidad} u., reintegro {importe(resultado.importe_reintegrado)} en {ETIQUETA_MEDIO[resultado.medio_codigo].toLowerCase()}.
          </p>
        )}
      </div>
    </Seccion>
  )
}
