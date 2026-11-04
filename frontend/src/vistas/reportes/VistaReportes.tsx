import { useState } from "react"
import { FileDownIcon, PlayIcon } from "lucide-react"

import { Campo, EstadoConsulta, MensajeError, Seccion, Seleccion, num, type Opcion } from "@/components/comunes"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAccion } from "@/hooks/useConsulta"
import { useCatalogos } from "@/hooks/useCatalogos"
import { api, urlPdf } from "@/lib/api"
import { fechaHora, hoyISO, importe, porcentaje, primerDiaDelMesISO } from "@/lib/formato"
import type { NombreReporte, Reporte } from "@/lib/tipos"

type TipoColumna = "texto" | "entero" | "importe" | "porcentaje"
type Columna = [titulo: string, clave: string, tipo: TipoColumna]

const REPORTES: { valor: NombreReporte; etiqueta: string; conPeriodo: boolean; columnas: Columna[]; descripcion: string }[] = [
  {
    valor: "ventas", etiqueta: "R1 · Ventas e ingresos", conPeriodo: true,
    descripcion: "Cobrado, reintegrado e ingreso neto por local y medio de pago. Cada flujo cuenta por su propia fecha. El PDF incluye el gráfico.",
    columnas: [["Local", "local_nombre", "texto"], ["Medio", "medio_codigo", "texto"], ["Ventas", "cantidad_ventas", "entero"],
      ["Cobrado", "cobrado", "importe"], ["Reintegrado", "reintegrado", "importe"], ["Ingreso neto", "neto", "importe"]],
  },
  {
    valor: "productos", etiqueta: "R2 · Productos y margen", conPeriodo: true,
    descripcion: "Ranking por unidades netas de devoluciones y margen estimado con importes y costos históricos.",
    columnas: [["#", "posicion", "entero"], ["Producto", "producto_nombre", "texto"], ["Vendidas", "vendidas", "entero"],
      ["Devueltas", "devueltas", "entero"], ["No aptas", "devueltas_no_aptas", "entero"], ["Netas", "unidades_netas", "entero"],
      ["Importe neto", "importe_neto", "importe"], ["Costo neto", "costo_neto", "importe"], ["Margen", "margen", "importe"]],
  },
  {
    valor: "existencias", etiqueta: "R3 · Existencias y mínimos", conPeriodo: false,
    descripcion: "Situación actual: disponible, faltante para el mínimo y mercadería en el circuito logístico (no habilitada para la venta).",
    columnas: [["Establecimiento", "sucursal_nombre", "texto"], ["Producto", "producto_nombre", "texto"], ["Disponible", "disponible", "entero"],
      ["Mínimo", "minimo", "entero"], ["Faltante", "faltante", "entero"], ["Comprometido", "comprometido_salida", "entero"],
      ["Por despachar", "pendiente_despacho", "entero"], ["En tránsito", "en_transito", "entero"],
      ["Sin verificar", "recibido_sin_verificar", "entero"], ["Rechazado", "rechazado", "entero"], ["Dev. no apta", "devuelto_no_apto", "entero"]],
  },
  {
    valor: "rechazos", etiqueta: "R4 · Rechazos de bultos", conPeriodo: true,
    descripcion: "Porcentaje de bultos rechazados sobre los finalizados en el período, por destino y por motivo.",
    columnas: [["Destino", "destino_nombre", "texto"], ["Verificados", "verificados", "entero"], ["Rechazados", "rechazados", "entero"],
      ["Finalizados", "finalizados", "entero"], ["% rechazo", "porcentaje_rechazo", "porcentaje"], ["Unid. rechazadas", "unidades_rechazadas", "entero"]],
  },
]

const MEDIOS: Opcion[] = [{ valor: "", etiqueta: "Todos" }, { valor: "EFECTIVO", etiqueta: "Efectivo" }, { valor: "TARJETA", etiqueta: "Tarjeta" }]

function mostrar(valor: unknown, tipo: TipoColumna): string {
  if (tipo === "importe") return importe(valor as string)
  if (tipo === "porcentaje") return porcentaje(valor as string | null)
  return valor === null || valor === undefined ? "—" : String(valor)
}

export function VistaReportes() {
  const catalogos = useCatalogos()
  const [nombre, setNombre] = useState<NombreReporte>("ventas")
  const [desde, setDesde] = useState(primerDiaDelMesISO())
  const [hasta, setHasta] = useState(hoyISO())
  const [local, setLocal] = useState("")
  const [medio, setMedio] = useState("")
  const [sucursal, setSucursal] = useState("")
  const [producto, setProducto] = useState("")
  const [soloBajoMinimo, setSoloBajoMinimo] = useState(false)
  const [resultado, setResultado] = useState<{ datos: Reporte; filtros: Record<string, string | boolean> } | null>(null)
  const { ejecutar, pendiente, error } = useAccion()

  const definicion = REPORTES.find((r) => r.valor === nombre)!
  const todos = (opciones: Opcion[]) => [{ valor: "", etiqueta: "Todos" }, ...opciones]

  const filtrosActuales = (): Record<string, string | boolean> => {
    const periodo = { desde, hasta }
    switch (nombre) {
      case "ventas": return { ...periodo, local, medio }
      case "productos": return { ...periodo, local }
      case "existencias": return { sucursal, producto, solo_bajo_minimo: soloBajoMinimo }
      case "rechazos": return { ...periodo, destino: local }
    }
  }

  const consultar = async () => {
    const filtros = filtrosActuales()
    const datos = await ejecutar(() => api.reporte(nombre, filtros))
    if (datos) setResultado({ datos, filtros })
  }

  const elegirReporte = (valor: string) => {
    setNombre(valor as NombreReporte)
    setResultado(null)
  }

  const vigente = resultado?.datos.reporte === nombre ? resultado : null
  const maximoGrafico = Math.max(1, ...(vigente?.datos.grafico ?? []).map((b) => Math.abs(Number(b.neto))))

  return (
    <div className="space-y-6">
      <Seccion titulo="Reportes" descripcion={definicion.descripcion}>
        <form className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" onSubmit={(e) => { e.preventDefault(); void consultar() }}>
          <Campo etiqueta="Reporte" className="sm:col-span-2 lg:col-span-1">
            <Seleccion valor={nombre} onCambio={elegirReporte} opciones={REPORTES.map((r) => ({ valor: r.valor, etiqueta: r.etiqueta }))} />
          </Campo>
          {definicion.conPeriodo && (
            <>
              <Campo etiqueta="Desde" htmlFor="rep-desde"><Input id="rep-desde" type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></Campo>
              <Campo etiqueta="Hasta" htmlFor="rep-hasta"><Input id="rep-hasta" type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></Campo>
            </>
          )}
          {nombre !== "existencias" && (
            <Campo etiqueta={nombre === "rechazos" ? "Destino" : "Local"}>
              <Seleccion valor={local} onCambio={setLocal} opciones={todos(catalogos.opcionesLocales)} />
            </Campo>
          )}
          {nombre === "ventas" && <Campo etiqueta="Medio de pago"><Seleccion valor={medio} onCambio={setMedio} opciones={MEDIOS} /></Campo>}
          {nombre === "existencias" && (
            <>
              <Campo etiqueta="Establecimiento"><Seleccion valor={sucursal} onCambio={setSucursal} opciones={todos(catalogos.opcionesSucursales)} /></Campo>
              <Campo etiqueta="Producto"><Seleccion valor={producto} onCambio={setProducto} opciones={todos(catalogos.opcionesProductos)} /></Campo>
              <label className="flex items-end gap-2 pb-2 text-sm">
                <Checkbox checked={soloBajoMinimo} onCheckedChange={setSoloBajoMinimo} /> Sólo debajo del mínimo
              </label>
            </>
          )}
          <div className="flex items-end gap-2 sm:col-span-2 lg:col-span-4">
            <Button type="submit" disabled={pendiente}><PlayIcon data-icon="inline-start" /> {pendiente ? "Consultando…" : "Consultar"}</Button>
            {vigente && (
              // El PDF usa exactamente los filtros de la consulta mostrada.
              <a className={buttonVariants({ variant: "outline" })} href={urlPdf(`/reportes/${nombre}/pdf`, vigente.filtros)}>
                <FileDownIcon data-icon="inline-start" /> Descargar PDF
              </a>
            )}
          </div>
        </form>
        <div className="mt-4"><MensajeError error={error} titulo="No se pudo generar el reporte" /></div>
      </Seccion>

      {vigente && (
        <Seccion titulo={vigente.datos.titulo} descripcion={`Generado ${fechaHora(vigente.datos.generado)}`}
          acciones={Object.entries(vigente.datos.filtros).map(([k, v]) => <Badge key={k} variant="outline">{k}: {String(v)}</Badge>)}>
          <EstadoConsulta cargando={false} error={null} vacio={vigente.datos.filas.length === 0} mensajeVacio="Sin movimientos para los filtros elegidos.">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>{definicion.columnas.map(([t, c, tipo]) => <TableHead key={c} className={tipo === "texto" ? undefined : num}>{t}</TableHead>)}</TableRow>
                </TableHeader>
                <TableBody>
                  {vigente.datos.filas.map((fila, i) => (
                    <TableRow key={i}>
                      {definicion.columnas.map(([, c, tipo]) => (
                        <TableCell key={c} className={tipo === "texto" ? undefined : num}>{mostrar(fila[c], tipo)}</TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
                <TableFooter>
                  <TableRow>
                    {definicion.columnas.map(([, c, tipo], i) => (
                      <TableCell key={c} className={tipo === "texto" ? undefined : num}>
                        {i === 0 ? "Total" : c in vigente.datos.totales ? mostrar(vigente.datos.totales[c], tipo) : ""}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableFooter>
              </Table>
            </div>

            {nombre === "ventas" && (vigente.datos.grafico ?? []).length > 0 && (
              <div className="mt-6 space-y-2">
                <h3 className="text-sm font-medium">Ingreso neto por local</h3>
                {vigente.datos.grafico!.map((barra) => (
                  <div key={barra.local_codigo} className="grid grid-cols-[10rem_1fr_8rem] items-center gap-3 text-sm">
                    <span className="truncate">{barra.local_nombre}</span>
                    <div className="h-3 rounded bg-muted">
                      <div className={Number(barra.neto) < 0 ? "h-3 rounded bg-destructive" : "h-3 rounded bg-primary"}
                        style={{ width: `${(Math.abs(Number(barra.neto)) / maximoGrafico) * 100}%` }} />
                    </div>
                    <span className={num}>{importe(barra.neto)}</span>
                  </div>
                ))}
              </div>
            )}

            {nombre === "rechazos" && (vigente.datos.motivos ?? []).length > 0 && (
              <div className="mt-6">
                <h3 className="mb-2 text-sm font-medium">Rechazos por motivo</h3>
                <Table>
                  <TableHeader>
                    <TableRow><TableHead>Destino</TableHead><TableHead>Motivo</TableHead><TableHead className={num}>Bultos</TableHead><TableHead className={num}>Unidades</TableHead></TableRow>
                  </TableHeader>
                  <TableBody>
                    {vigente.datos.motivos!.map((m) => (
                      <TableRow key={`${m.destino_codigo}-${m.motivo}`}>
                        <TableCell>{m.destino_nombre}</TableCell><TableCell>{m.motivo}</TableCell>
                        <TableCell className={num}>{m.bultos}</TableCell><TableCell className={num}>{m.unidades}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </EstadoConsulta>
        </Seccion>
      )}
    </div>
  )
}
