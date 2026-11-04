import type { ReactNode } from "react"
import { AlertCircleIcon, Loader2Icon, WifiOffIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { describirError, ErrorRed } from "@/lib/api"
import { ETIQUETA_ESTADO } from "@/lib/formato"
import type { EstadoBulto } from "@/lib/tipos"
import { cn } from "@/lib/utils"

export function Seccion({ titulo, descripcion, acciones, children, className }: {
  titulo: string
  descripcion?: string
  acciones?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1">
          <CardTitle>{titulo}</CardTitle>
          {descripcion && <CardDescription>{descripcion}</CardDescription>}
        </div>
        {acciones && <div className="flex shrink-0 flex-wrap items-center gap-2">{acciones}</div>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

/** Error de la API con sus detalles (fila y campo cuando corresponde). */
export function MensajeError({ error, titulo = "No se pudo completar la operación" }: { error: unknown; titulo?: string }) {
  if (!error) return null
  const { mensaje, detalles } = describirError(error)
  const sinConexion = error instanceof ErrorRed
  return (
    <Alert variant="destructive">
      {sinConexion ? <WifiOffIcon /> : <AlertCircleIcon />}
      <AlertTitle>{sinConexion ? "Sin respuesta del servidor" : titulo}</AlertTitle>
      <AlertDescription>
        <p>{mensaje}</p>
        {detalles.length > 0 && (
          <ul className="mt-1 list-disc pl-4">
            {detalles.map((d, i) => (
              <li key={i}>
                {d.fila ? `Fila ${d.fila}: ` : ""}
                {d.mensaje}
              </li>
            ))}
          </ul>
        )}
      </AlertDescription>
    </Alert>
  )
}

/** Envuelve una consulta: muestra carga, error o vacío; si hay datos, muestra el contenido. */
export function EstadoConsulta({ cargando, error, vacio, mensajeVacio = "No hay datos para mostrar.", children }: {
  cargando: boolean
  error: unknown
  vacio?: boolean
  mensajeVacio?: string
  children: ReactNode
}) {
  if (error) return <MensajeError error={error} titulo="No se pudieron cargar los datos" />
  if (cargando && vacio !== false) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" /> Cargando…
      </div>
    )
  }
  if (vacio) return <p className="py-6 text-center text-sm text-muted-foreground">{mensajeVacio}</p>
  return <>{children}</>
}

export function Campo({ etiqueta, htmlFor, ayuda, children, className }: {
  etiqueta: string
  htmlFor?: string
  ayuda?: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn("grid gap-1.5", className)}>
      <Label htmlFor={htmlFor}>{etiqueta}</Label>
      {children}
      {ayuda && <p className="text-xs text-muted-foreground">{ayuda}</p>}
    </div>
  )
}

export interface Opcion {
  valor: string
  etiqueta: string
}

/** Selector simple sobre el Select de shadcn/ui (Base UI). El valor "" representa "sin selección". */
export function Seleccion({ valor, onCambio, opciones, placeholder = "Elegir…", id, className, disabled }: {
  valor: string
  onCambio: (valor: string) => void
  opciones: Opcion[]
  placeholder?: string
  id?: string
  className?: string
  disabled?: boolean
}) {
  // Base UI usa null para "sin selección"; una opción con valor "" (por ejemplo "Todos") se muestra con su etiqueta.
  const items = opciones.map((o) => ({ value: o.valor === "" ? null : o.valor, label: o.etiqueta }))
  return (
    <Select items={items} value={valor === "" ? null : valor} onValueChange={(v) => onCambio((v as string | null) ?? "")} disabled={disabled}>
      <SelectTrigger id={id} className={cn("w-full", className)}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      {/* La lista puede ser más ancha que el selector para no recortar nombres largos. */}
      <SelectContent className="w-auto min-w-(--anchor-width)">
        {items.map((item) => (
          <SelectItem key={item.value ?? "_vacio"} value={item.value}>
            {item.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

const VARIANTE_ESTADO: Record<EstadoBulto, string> = {
  PREPARADO: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
  PRECINTADO: "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-200",
  EN_TRANSITO: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  RECIBIDO: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200",
  VERIFICADO: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  RECHAZADO: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-200",
}

export function BadgeEstado({ estado }: { estado: EstadoBulto }) {
  return <Badge className={VARIANTE_ESTADO[estado]}>{ETIQUETA_ESTADO[estado]}</Badge>
}

/** Celda numérica alineada a la derecha. */
export const num = "text-right tabular-nums"
