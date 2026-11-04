import { useState } from "react"
import { SaveIcon, UploadIcon } from "lucide-react"
import { toast } from "sonner"

import { Campo, EstadoConsulta, MensajeError, Seccion, Seleccion, num, type Opcion } from "@/components/comunes"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAccion, useConsulta } from "@/hooks/useConsulta"
import { api } from "@/lib/api"
import { generarNumero, importe } from "@/lib/formato"
import type { Ingreso, Producto, ResultadoImportacion, TipoImportacion } from "@/lib/tipos"

const TODOS: Opcion = { valor: "", etiqueta: "Todos" }

/** Disponible y mínimo por establecimiento. Sólo el mínimo es editable: el disponible cambia por operaciones. */
export function PanelExistencias({ opcionesSucursales, opcionesProductos }: {
  opcionesSucursales: Opcion[]
  opcionesProductos: Opcion[]
}) {
  const [sucursal, setSucursal] = useState("")
  const [producto, setProducto] = useState("")
  const [soloBajoMinimo, setSoloBajoMinimo] = useState(false)
  const { datos, cargando, error, recargar } = useConsulta(() => api.existencias({ sucursal, producto }), [sucursal, producto])
  const [minimos, setMinimos] = useState<Record<string, string>>({})
  const { ejecutar, pendiente, error: errorGuardar } = useAccion()

  const filas = (datos ?? []).filter((e) => !soloBajoMinimo || e.faltante > 0)
  const clave = (s: string, p: string) => `${s}|${p}`

  const guardarMinimo = async (s: string, p: string) => {
    const valor = Number(minimos[clave(s, p)])
    const resultado = await ejecutar(() => api.configurarMinimo(s, p, valor))
    if (resultado) {
      toast.success(`Mínimo de ${p} en ${s}: ${resultado.minimo}`)
      setMinimos(({ [clave(s, p)]: _, ...resto }) => resto)
      void recargar()
    }
  }

  return (
    <Seccion titulo="Existencias" descripcion="Disponible habilitado para la venta. Lo que está en tránsito o sin verificar se ve en el reporte de existencias.">
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Campo etiqueta="Establecimiento"><Seleccion valor={sucursal} onCambio={setSucursal} opciones={[TODOS, ...opcionesSucursales]} /></Campo>
        <Campo etiqueta="Producto"><Seleccion valor={producto} onCambio={setProducto} opciones={[TODOS, ...opcionesProductos]} /></Campo>
        <label className="flex items-end gap-2 pb-2 text-sm">
          <Checkbox checked={soloBajoMinimo} onCheckedChange={setSoloBajoMinimo} /> Sólo debajo del mínimo
        </label>
      </div>
      <MensajeError error={errorGuardar} titulo="No se pudo guardar el mínimo" />
      <EstadoConsulta cargando={cargando} error={error} vacio={filas.length === 0}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Establecimiento</TableHead>
              <TableHead>Producto</TableHead>
              <TableHead className={num}>Disponible</TableHead>
              <TableHead className="w-40">Mínimo</TableHead>
              <TableHead className={num}>Faltante</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filas.map((e) => {
              const k = clave(e.sucursal_codigo, e.producto_codigo)
              const editado = minimos[k] !== undefined && minimos[k] !== String(e.minimo)
              return (
                <TableRow key={k}>
                  <TableCell>{e.sucursal_nombre}</TableCell>
                  <TableCell>{e.producto_codigo} · {e.producto_nombre}</TableCell>
                  <TableCell className={num}>{e.disponible}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Input className="h-7 w-20" inputMode="numeric" value={minimos[k] ?? String(e.minimo)}
                        onChange={(ev) => setMinimos({ ...minimos, [k]: ev.target.value })} aria-label={`Mínimo de ${e.producto_codigo}`} />
                      {editado && (
                        <Button size="icon-sm" variant="outline" disabled={pendiente} aria-label="Guardar mínimo"
                          onClick={() => void guardarMinimo(e.sucursal_codigo, e.producto_codigo)}>
                          <SaveIcon />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className={num}>
                    {e.faltante > 0 ? <Badge variant="destructive">{e.faltante}</Badge> : <span className="text-muted-foreground">0</span>}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </EstadoConsulta>
    </Seccion>
  )
}

/** Entrada simple de compra al CD. La fecha la asigna el servidor. */
export function FormularioIngreso({ productos, opcionesProductos, opcionesProveedores, alRegistrar }: {
  productos: Producto[]
  opcionesProductos: Opcion[]
  opcionesProveedores: Opcion[]
  alRegistrar: () => void
}) {
  const [numero, setNumero] = useState(() => generarNumero("ING"))
  const [producto, setProducto] = useState("")
  const [proveedor, setProveedor] = useState("")
  const [cantidad, setCantidad] = useState("")
  const [costo, setCosto] = useState("")
  const [resultado, setResultado] = useState<Ingreso | null>(null)
  const { ejecutar, pendiente, error } = useAccion()

  const elegirProducto = (codigo: string) => {
    setProducto(codigo)
    const elegido = productos.find((p) => p.codigo === codigo)
    if (elegido) {
      setProveedor(elegido.proveedor_codigo)
      setCosto(elegido.costo_referencia)
    }
  }

  const registrar = async () => {
    const ingreso = await ejecutar(() => api.registrarIngreso({
      numero, producto_codigo: producto, proveedor_codigo: proveedor, cantidad: Number(cantidad), costo_unitario: costo,
    }))
    if (ingreso) {
      setResultado(ingreso)
      toast.success(`Ingreso ${ingreso.numero} registrado en el CD`)
      setNumero(generarNumero("ING"))
      setCantidad("")
      alRegistrar()
    }
  }

  return (
    <Seccion titulo="Ingreso de mercadería al CD" descripcion="Suma stock al Centro de Distribución y actualiza el costo de referencia para ventas futuras.">
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); void registrar() }}>
        <Campo etiqueta="Número de ingreso" htmlFor="ing-numero"><Input id="ing-numero" value={numero} onChange={(e) => setNumero(e.target.value)} /></Campo>
        <Campo etiqueta="Producto"><Seleccion valor={producto} onCambio={elegirProducto} opciones={opcionesProductos} /></Campo>
        <Campo etiqueta="Proveedor"><Seleccion valor={proveedor} onCambio={setProveedor} opciones={opcionesProveedores} /></Campo>
        <Campo etiqueta="Cantidad" htmlFor="ing-cantidad"><Input id="ing-cantidad" inputMode="numeric" value={cantidad} onChange={(e) => setCantidad(e.target.value)} /></Campo>
        <Campo etiqueta="Costo unitario" htmlFor="ing-costo"><Input id="ing-costo" inputMode="decimal" value={costo} onChange={(e) => setCosto(e.target.value)} /></Campo>
        <div className="flex items-end">
          <Button type="submit" disabled={pendiente || !producto || !proveedor}>{pendiente ? "Registrando…" : "Registrar ingreso"}</Button>
        </div>
      </form>
      <div className="mt-4 space-y-3">
        <MensajeError error={error} titulo="No se registró el ingreso" />
        {resultado && (
          <p className="text-sm text-muted-foreground">
            Último ingreso: <strong>{resultado.numero}</strong> · {resultado.cantidad} u. de {resultado.producto_codigo} · {importe(resultado.importe)}
          </p>
        )}
      </div>
    </Seccion>
  )
}

const TIPOS_IMPORTACION: { valor: TipoImportacion; etiqueta: string; columnas: string }[] = [
  { valor: "proveedores", etiqueta: "Proveedores", columnas: "codigo, nombre" },
  { valor: "sucursales", etiqueta: "Establecimientos", columnas: "codigo, nombre, es_cd" },
  { valor: "productos", etiqueta: "Productos", columnas: "codigo, nombre, categoria, proveedor_codigo, precio, costo_referencia" },
  { valor: "ingresos", etiqueta: "Stock inicial (ingresos al CD)", columnas: "numero, producto_codigo, proveedor_codigo, cantidad, costo_unitario" },
  { valor: "minimos", etiqueta: "Mínimos", columnas: "sucursal_codigo, producto_codigo, minimo" },
]

/** Sube un CSV. Se valida completo en el servidor: si una fila falla no se importa ninguna. */
export function ImportarCSV({ alImportar }: { alImportar: () => void }) {
  const [tipo, setTipo] = useState<TipoImportacion>("productos")
  const [archivo, setArchivo] = useState<File | null>(null)
  const [resultado, setResultado] = useState<ResultadoImportacion | null>(null)
  const { ejecutar, pendiente, error } = useAccion()
  const definicion = TIPOS_IMPORTACION.find((t) => t.valor === tipo)!

  const importar = async () => {
    if (!archivo) return
    setResultado(null)
    const respuesta = await ejecutar(() => api.importar(tipo, archivo))
    if (respuesta) {
      setResultado(respuesta)
      toast.success(`Se importaron ${respuesta.filas_importadas} filas`)
      alImportar()
    }
  }

  return (
    <Seccion titulo="Importar CSV" descripcion="Separador coma o punto y coma, codificación UTF-8. La primera fila es el encabezado.">
      <form className="grid gap-3 sm:grid-cols-3" onSubmit={(e) => { e.preventDefault(); void importar() }}>
        <Campo etiqueta="Tipo de archivo" ayuda={`Columnas: ${definicion.columnas}`}>
          <Seleccion valor={tipo} onCambio={(v) => setTipo(v as TipoImportacion)} opciones={TIPOS_IMPORTACION} />
        </Campo>
        <Campo etiqueta="Archivo" htmlFor="csv-archivo">
          <Input id="csv-archivo" type="file" accept=".csv,text/csv" onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
        </Campo>
        <div className="flex items-start pt-6">
          <Button type="submit" disabled={!archivo || pendiente}>
            <UploadIcon data-icon="inline-start" /> {pendiente ? "Importando…" : "Importar"}
          </Button>
        </div>
      </form>
      <div className="mt-4">
        <MensajeError error={error} titulo="No se importó ninguna fila" />
        {resultado && <p className="text-sm">Importación completa: {resultado.filas_importadas} filas de {resultado.tipo}.</p>}
      </div>
    </Seccion>
  )
}
