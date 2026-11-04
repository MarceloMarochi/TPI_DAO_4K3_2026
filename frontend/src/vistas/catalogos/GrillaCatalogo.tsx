import { useState } from "react"
import { PencilIcon, PlusIcon, SearchIcon } from "lucide-react"
import { toast } from "sonner"

import { Campo, EstadoConsulta, MensajeError, Seccion, Seleccion, num } from "@/components/comunes"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAccion, useConsulta } from "@/hooks/useConsulta"
import { api } from "@/lib/api"
import { importe } from "@/lib/formato"
import type { Proveedor } from "@/lib/tipos"

type TipoCampo = "texto" | "importe" | "si_no" | "proveedor"
type Fila = Record<string, string | boolean>

interface DefinicionCampo {
  clave: string
  etiqueta: string
  tipo: TipoCampo
  soloAlta?: boolean // el código y si es CD no se modifican después del alta
}

export interface ConfiguracionCatalogo {
  tipo: "productos" | "sucursales" | "proveedores"
  titulo: string
  singular: string
  campos: DefinicionCampo[]
  columnas: DefinicionCampo[]
}

export const CATALOGOS: ConfiguracionCatalogo[] = [
  {
    tipo: "productos",
    titulo: "Productos",
    singular: "producto",
    campos: [
      { clave: "codigo", etiqueta: "Código", tipo: "texto", soloAlta: true },
      { clave: "nombre", etiqueta: "Nombre", tipo: "texto" },
      { clave: "categoria", etiqueta: "Categoría", tipo: "texto" },
      { clave: "proveedor_codigo", etiqueta: "Proveedor principal", tipo: "proveedor" },
      { clave: "precio", etiqueta: "Precio de venta", tipo: "importe" },
      { clave: "costo_referencia", etiqueta: "Costo de referencia", tipo: "importe" },
    ],
    columnas: [
      { clave: "codigo", etiqueta: "Código", tipo: "texto" },
      { clave: "nombre", etiqueta: "Nombre", tipo: "texto" },
      { clave: "categoria", etiqueta: "Categoría", tipo: "texto" },
      { clave: "proveedor_codigo", etiqueta: "Proveedor", tipo: "texto" },
      { clave: "precio", etiqueta: "Precio", tipo: "importe" },
      { clave: "costo_referencia", etiqueta: "Costo ref.", tipo: "importe" },
    ],
  },
  {
    tipo: "sucursales",
    titulo: "Establecimientos",
    singular: "establecimiento",
    campos: [
      { clave: "codigo", etiqueta: "Código", tipo: "texto", soloAlta: true },
      { clave: "nombre", etiqueta: "Nombre", tipo: "texto" },
      { clave: "es_cd", etiqueta: "Es el Centro de Distribución", tipo: "si_no", soloAlta: true },
    ],
    columnas: [
      { clave: "codigo", etiqueta: "Código", tipo: "texto" },
      { clave: "nombre", etiqueta: "Nombre", tipo: "texto" },
      { clave: "es_cd", etiqueta: "Tipo", tipo: "si_no" },
    ],
  },
  {
    tipo: "proveedores",
    titulo: "Proveedores",
    singular: "proveedor",
    campos: [
      { clave: "codigo", etiqueta: "Código", tipo: "texto", soloAlta: true },
      { clave: "nombre", etiqueta: "Nombre", tipo: "texto" },
    ],
    columnas: [
      { clave: "codigo", etiqueta: "Código", tipo: "texto" },
      { clave: "nombre", etiqueta: "Nombre", tipo: "texto" },
    ],
  },
]

const listar = {
  productos: api.productos,
  sucursales: api.sucursales,
  proveedores: api.proveedores,
} as const

/** Grilla compartida por los tres catálogos: búsqueda, alta y edición. No hay bajas (los códigos referenciados se conservan). */
export function GrillaCatalogo({ config, proveedores, alCambiar }: {
  config: ConfiguracionCatalogo
  proveedores: Proveedor[]
  alCambiar: () => void
}) {
  const { datos, cargando, error, recargar } = useConsulta(
    () => listar[config.tipo]() as unknown as Promise<Fila[]>, [config.tipo])
  const [busqueda, setBusqueda] = useState("")
  const [edicion, setEdicion] = useState<{ fila: Fila | null } | null>(null)

  const texto = busqueda.trim().toLowerCase()
  const filas = (datos ?? []).filter(
    (fila) => !texto || Object.values(fila).some((v) => String(v).toLowerCase().includes(texto)))

  return (
    <Seccion
      titulo={config.titulo}
      descripcion="Alta y edición. Los códigos no se modifican y los registros referenciados no se eliminan."
      acciones={
        <>
          <div className="relative">
            <SearchIcon className="absolute top-2 left-2 size-4 text-muted-foreground" />
            <Input className="w-48 pl-8" placeholder="Buscar…" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
          </div>
          <Button onClick={() => setEdicion({ fila: null })}>
            <PlusIcon data-icon="inline-start" /> Nuevo
          </Button>
        </>
      }
    >
      <EstadoConsulta cargando={cargando} error={error} vacio={filas.length === 0}
        mensajeVacio={texto ? "Ningún registro coincide con la búsqueda." : "Todavía no hay registros."}>
        <Table>
          <TableHeader>
            <TableRow>
              {config.columnas.map((c) => (
                <TableHead key={c.clave} className={c.tipo === "importe" ? num : undefined}>{c.etiqueta}</TableHead>
              ))}
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {filas.map((fila) => (
              <TableRow key={String(fila.codigo)}>
                {config.columnas.map((c) => (
                  <TableCell key={c.clave} className={c.tipo === "importe" ? num : undefined}>
                    {c.tipo === "importe" ? importe(String(fila[c.clave])) : c.tipo === "si_no" ? (fila[c.clave] ? "Centro de Distribución" : "Local") : String(fila[c.clave])}
                  </TableCell>
                ))}
                <TableCell>
                  <Button variant="ghost" size="icon-sm" aria-label={`Editar ${fila.codigo}`} onClick={() => setEdicion({ fila })}>
                    <PencilIcon />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </EstadoConsulta>

      {edicion && (
        <FormularioCatalogo
          config={config}
          fila={edicion.fila}
          proveedores={proveedores}
          alCerrar={() => setEdicion(null)}
          alGuardar={() => {
            setEdicion(null)
            void recargar()
            alCambiar()
          }}
        />
      )}
    </Seccion>
  )
}

function FormularioCatalogo({ config, fila, proveedores, alCerrar, alGuardar }: {
  config: ConfiguracionCatalogo
  fila: Fila | null
  proveedores: Proveedor[]
  alCerrar: () => void
  alGuardar: () => void
}) {
  const esAlta = fila === null
  const [valores, setValores] = useState<Fila>(() =>
    Object.fromEntries(config.campos.map((c) => [c.clave, fila?.[c.clave] ?? (c.tipo === "si_no" ? false : "")])))
  const { ejecutar, pendiente, error } = useAccion()

  const guardar = async () => {
    const campos = config.campos.filter((c) => esAlta || !c.soloAlta)
    const cuerpo = Object.fromEntries(campos.map((c) => [c.clave, valores[c.clave]]))
    const resultado = await ejecutar(() =>
      esAlta ? api.altaCatalogo(config.tipo, cuerpo) : api.editarCatalogo(config.tipo, String(fila.codigo), cuerpo))
    if (resultado) {
      toast.success(esAlta ? `Se dio de alta el ${config.singular}.` : `Se actualizó el ${config.singular}.`)
      alGuardar()
    }
  }

  return (
    <Dialog open onOpenChange={(abierto) => !abierto && alCerrar()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{esAlta ? `Nuevo ${config.singular}` : `Editar ${config.singular} ${fila.codigo}`}</DialogTitle>
          <DialogDescription>El servidor valida duplicados, referencias e importes.</DialogDescription>
        </DialogHeader>
        <form id="form-catalogo" className="grid gap-3" onSubmit={(e) => { e.preventDefault(); void guardar() }}>
          {config.campos.filter((c) => esAlta || !c.soloAlta).map((c) => {
            const id = `campo-${c.clave}`
            if (c.tipo === "si_no") {
              return (
                <label key={c.clave} className="flex items-center gap-2 text-sm">
                  <Checkbox checked={Boolean(valores[c.clave])} onCheckedChange={(v) => setValores({ ...valores, [c.clave]: v })} />
                  {c.etiqueta}
                </label>
              )
            }
            return (
              <Campo key={c.clave} etiqueta={c.etiqueta} htmlFor={id}>
                {c.tipo === "proveedor" ? (
                  <Seleccion id={id} valor={String(valores[c.clave])} onCambio={(v) => setValores({ ...valores, [c.clave]: v })}
                    opciones={proveedores.map((p) => ({ valor: p.codigo, etiqueta: `${p.codigo} · ${p.nombre}` }))} />
                ) : (
                  <Input id={id} value={String(valores[c.clave])} inputMode={c.tipo === "importe" ? "decimal" : undefined}
                    placeholder={c.tipo === "importe" ? "0.00" : undefined}
                    onChange={(e) => setValores({ ...valores, [c.clave]: e.target.value })} />
                )}
              </Campo>
            )
          })}
        </form>
        <MensajeError error={error} titulo="No se pudo guardar" />
        <DialogFooter>
          <Button variant="outline" onClick={alCerrar}>Cancelar</Button>
          <Button type="submit" form="form-catalogo" disabled={pendiente}>{pendiente ? "Guardando…" : "Guardar"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
