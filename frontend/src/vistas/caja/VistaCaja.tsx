import { StoreIcon } from "lucide-react"

import { EstadoConsulta } from "@/components/comunes"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCatalogos } from "@/hooks/useCatalogos"
import { useContexto } from "@/store/contexto"
import { PanelDevoluciones } from "./PanelDevoluciones"
import { PanelVenta } from "./PanelVenta"

export function VistaCaja() {
  const catalogos = useCatalogos()
  // La caja sólo se muestra cuando se opera en un local (ver lib/contextoOperativo.ts).
  const localCodigo = useContexto((s) => s.sucursalCodigo)

  if (!localCodigo) {
    return (
      <Alert>
        <StoreIcon />
        <AlertTitle>Elegí un local</AlertTitle>
        <AlertDescription>La caja vende y registra devoluciones en el local en el que se opera.</AlertDescription>
      </Alert>
    )
  }

  return (
    <EstadoConsulta cargando={catalogos.cargando && !catalogos.datos} error={catalogos.error}>
      <Tabs defaultValue="venta">
        <TabsList variant="line" className="mb-4">
          <TabsTrigger value="venta">Venta</TabsTrigger>
          <TabsTrigger value="devoluciones">Devoluciones</TabsTrigger>
        </TabsList>
        <TabsContent value="venta"><PanelVenta key={localCodigo} localCodigo={localCodigo} productos={catalogos.productos} /></TabsContent>
        <TabsContent value="devoluciones"><PanelDevoluciones key={localCodigo} localCodigo={localCodigo} /></TabsContent>
      </Tabs>
    </EstadoConsulta>
  )
}
