import { useState } from "react"
import { CheckCircle2Icon, FileDownIcon, MinusIcon, PlusIcon, SearchIcon, Trash2Icon } from "lucide-react"
import { toast } from "sonner"

import { Campo, EstadoConsulta, MensajeError, Seccion, Seleccion, num } from "@/components/comunes"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAccion, useConsulta } from "@/hooks/useConsulta"
import { api, ErrorApi, ErrorRed, urlPdf } from "@/lib/api"
import { ETIQUETA_MEDIO, importe, tasa } from "@/lib/formato"
import type { CodigoMedio, Cotizacion, Producto, Venta } from "@/lib/tipos"
import { useContexto } from "@/store/contexto"

export function PanelVenta({ localCodigo, productos }: { localCodigo: string; productos: Producto[] }) {
  const { borrador, agregarItem, cambiarCantidad, quitarItem, cambiarMedio, descartarBorrador } = useContexto()
  const existencias = useConsulta(() => api.existencias({ sucursal: localCodigo }), [localCodigo])
  const medios = useConsulta(() => api.mediosPago(), [])
  const [busqueda, setBusqueda] = useState("")
  const [cotizacion, setCotizacion] = useState<{ datos: Cotizacion; version: number } | null>(null)
  const [confirmada, setConfirmada] = useState<Venta | null>(null)
  const accionCotizar = useAccion()
  const accionConfirmar = useAccion()

  const disponible = (codigo: string) =>
    existencias.datos?.find((e) => e.producto_codigo === codigo)?.disponible ?? 0
  const texto = busqueda.trim().toLowerCase()
  const candidatos = productos
    .filter((p) => disponible(p.codigo) > 0)
    .filter((p) => !texto || `${p.codigo} ${p.nombre} ${p.categoria}`.toLowerCase().includes(texto))

  // Cualquier edición del borrador cambia su versión y deja vencida la cotización anterior.
  const cotizacionVigente = cotizacion && cotizacion.version === borrador.version ? cotizacion.datos : null
  const items = borrador.items.map((i) => ({ producto_codigo: i.producto_codigo, cantidad: i.cantidad }))

  const cotizar = async () => {
    const version = borrador.version
    const datos = await accionCotizar.ejecutar(() => api.cotizar({ local_codigo: localCodigo, medio_codigo: borrador.medio, items }))
    if (datos) setCotizacion({ datos, version })
  }

  const terminar = (venta: Venta) => {
    setConfirmada(venta)
    setCotizacion(null)
    accionConfirmar.limpiarError()
    descartarBorrador()
    void existencias.recargar()
    toast.success(`Venta ${venta.numero} confirmada: ${importe(venta.total_cobrado)}`)
  }

  const confirmar = async () => {
    if (!cotizacionVigente) return
    setConfirmada(null)
    const venta = await accionConfirmar.ejecutar(() => api.confirmarVenta({
      numero: borrador.numero, local_codigo: localCodigo, medio_codigo: borrador.medio, items,
      total_esperado: cotizacionVigente.total,
    }))
    if (venta) terminar(venta)
  }

  // Si se perdió la respuesta, se consulta por el MISMO número antes de reintentar (no se genera otro).
  const consultarSiQuedoRegistrada = async () => {
    try {
      terminar(await api.venta(borrador.numero))
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 404) {
        accionConfirmar.limpiarError()
        toast.info("La venta no quedó registrada. Podés volver a confirmarla con el mismo número.")
      } else {
        toast.error("Todavía no hay conexión con el servidor.")
      }
    }
  }

  const errorConfirmar = accionConfirmar.error
  // Sin respuesta del servidor: no se sabe si la venta quedó registrada; hay que consultar antes de reintentar.
  const sinRespuesta = errorConfirmar instanceof ErrorRed

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_3fr]">
      <Seccion titulo="Productos disponibles" descripcion="Sólo mercadería verificada en este local.">
        <div className="relative mb-3">
          <SearchIcon className="absolute top-2 left-2 size-4 text-muted-foreground" />
          <Input className="pl-8" placeholder="Buscar por código, nombre o categoría" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
        </div>
        <EstadoConsulta cargando={existencias.cargando} error={existencias.error} vacio={candidatos.length === 0}
          mensajeVacio="Este local no tiene stock disponible. Llega con bultos verificados desde el CD.">
          <ul className="max-h-[28rem] divide-y overflow-auto">
            {candidatos.map((p) => (
              <li key={p.codigo} className="flex items-center justify-between gap-2 py-2 text-sm">
                <div>
                  <p className="font-medium">{p.nombre}</p>
                  <p className="text-muted-foreground">{p.codigo} · {importe(p.precio)} · disponible {disponible(p.codigo)}</p>
                </div>
                <Button size="sm" variant="outline" onClick={() => agregarItem({ producto_codigo: p.codigo, producto_nombre: p.nombre, precio: p.precio })}>
                  <PlusIcon data-icon="inline-start" /> Agregar
                </Button>
              </li>
            ))}
          </ul>
        </EstadoConsulta>
      </Seccion>

      <div className="space-y-6">
        <Seccion titulo="Venta en preparación" descripcion={`Número ${borrador.numero}`}
          acciones={borrador.items.length > 0 && (
            <Button variant="ghost" size="sm" onClick={() => { descartarBorrador(); setCotizacion(null) }}>Descartar</Button>
          )}>
          {borrador.items.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">Agregá productos desde la lista.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Producto</TableHead>
                  <TableHead className={num}>Precio</TableHead>
                  <TableHead className="w-36 text-center">Cantidad</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {borrador.items.map((i) => (
                  <TableRow key={i.producto_codigo}>
                    <TableCell>{i.producto_nombre}</TableCell>
                    <TableCell className={num}>{importe(i.precio)}</TableCell>
                    <TableCell>
                      <div className="flex items-center justify-center gap-1">
                        <Button size="icon-xs" variant="outline" aria-label="Restar" disabled={i.cantidad <= 1}
                          onClick={() => cambiarCantidad(i.producto_codigo, i.cantidad - 1)}><MinusIcon /></Button>
                        <Input className="h-6 w-14 text-center" inputMode="numeric" value={i.cantidad} aria-label={`Cantidad de ${i.producto_codigo}`}
                          onChange={(e) => cambiarCantidad(i.producto_codigo, Math.max(1, Number(e.target.value) || 1))} />
                        <Button size="icon-xs" variant="outline" aria-label="Sumar"
                          onClick={() => cambiarCantidad(i.producto_codigo, i.cantidad + 1)}><PlusIcon /></Button>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Button size="icon-sm" variant="ghost" aria-label="Quitar" onClick={() => quitarItem(i.producto_codigo)}><Trash2Icon /></Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          <Separator className="my-4" />
          <div className="grid items-end gap-3 sm:grid-cols-[1fr_auto]">
            <Campo etiqueta="Medio de pago">
              <Seleccion valor={borrador.medio} onCambio={(v) => cambiarMedio(v as CodigoMedio)}
                opciones={(medios.datos ?? []).map((m) => ({
                  valor: m.codigo, etiqueta: `${ETIQUETA_MEDIO[m.codigo]} (${m.tipo} ${tasa(m.tasa)})`,
                }))} />
            </Campo>
            <Button variant="outline" disabled={borrador.items.length === 0 || accionCotizar.pendiente} onClick={() => void cotizar()}>
              {accionCotizar.pendiente ? "Cotizando…" : "Cotizar"}
            </Button>
          </div>
          <div className="mt-3"><MensajeError error={accionCotizar.error} titulo="No se pudo cotizar" /></div>
        </Seccion>

        <Seccion titulo="Total" descripcion="Calculado por el servidor. Cotizar no reserva stock.">
          {cotizacionVigente ? (
            <dl className="grid grid-cols-2 gap-y-1 text-sm">
              <dt>Subtotal</dt><dd className={num}>{importe(cotizacionVigente.subtotal)}</dd>
              <dt>{Number(cotizacionVigente.ajuste) < 0 ? "Descuento" : "Recargo"} ({tasa(cotizacionVigente.tasa)})</dt>
              <dd className={num}>{importe(cotizacionVigente.ajuste)}</dd>
              <dt className="text-base font-semibold">Total</dt><dd className={`${num} text-base font-semibold`}>{importe(cotizacionVigente.total)}</dd>
            </dl>
          ) : (
            <p className="text-sm text-muted-foreground">
              {cotizacion ? "La venta cambió desde la última cotización: volvé a cotizar." : "Cotizá la venta para ver el total."}
            </p>
          )}
          <Button className="mt-4 w-full" size="lg" disabled={!cotizacionVigente || accionConfirmar.pendiente || sinRespuesta}
            onClick={() => void confirmar()}>
            {accionConfirmar.pendiente ? "Confirmando…" : "Confirmar venta"}
          </Button>
          <div className="mt-3 space-y-3">
            {sinRespuesta ? (
              <Alert>
                <AlertTitle>No sabemos si la venta quedó registrada</AlertTitle>
                <AlertDescription>
                  <p>Se perdió la comunicación con el servidor. Consultá el estado de la venta {borrador.numero} antes de reintentar.</p>
                  <Button size="sm" className="mt-2" onClick={() => void consultarSiQuedoRegistrada()}>Consultar estado</Button>
                </AlertDescription>
              </Alert>
            ) : (
              <MensajeError error={errorConfirmar} titulo="No se registró la venta" />
            )}
            {confirmada && (
              <Alert>
                <CheckCircle2Icon />
                <AlertTitle>Venta {confirmada.numero} registrada · {importe(confirmada.total_cobrado)}</AlertTitle>
                <AlertDescription>
                  <a className="mt-1 inline-flex items-center gap-1 underline" href={urlPdf(`/ventas/${encodeURIComponent(confirmada.numero)}/comprobante`)}>
                    <FileDownIcon className="size-4" /> Descargar comprobante {confirmada.comprobante_numero}
                  </a>
                </AlertDescription>
              </Alert>
            )}
          </div>
        </Seccion>
      </div>
    </div>
  )
}
