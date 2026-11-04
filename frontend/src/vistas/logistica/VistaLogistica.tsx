import { useState } from "react"

import { EstadoConsulta } from "@/components/comunes"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCatalogos } from "@/hooks/useCatalogos"
import { PanelBultos } from "./PanelBultos"
import { PanelOrdenes } from "./PanelOrdenes"

export function VistaLogistica() {
  const catalogos = useCatalogos()
  const [pestania, setPestania] = useState("ordenes")
  const [bultoNuevo, setBultoNuevo] = useState<string | null>(null)

  return (
    <EstadoConsulta cargando={catalogos.cargando && !catalogos.datos} error={catalogos.error}>
      <Tabs value={pestania} onValueChange={(v) => setPestania(String(v))}>
        <TabsList variant="line" className="mb-4">
          <TabsTrigger value="ordenes">Órdenes y preparación</TabsTrigger>
          <TabsTrigger value="bultos">Seguimiento de bultos</TabsTrigger>
        </TabsList>
        <TabsContent value="ordenes">
          <PanelOrdenes opcionesLocales={catalogos.opcionesLocales} opcionesProductos={catalogos.opcionesProductos}
            nombreSucursal={catalogos.nombreSucursal}
            alPrepararBulto={(bulto) => { setBultoNuevo(bulto.codigo); setPestania("bultos") }} />
        </TabsContent>
        <TabsContent value="bultos">
          <PanelBultos key={bultoNuevo ?? "inicial"} opcionesLocales={catalogos.opcionesLocales}
            nombreSucursal={catalogos.nombreSucursal} seleccionInicial={bultoNuevo} />
        </TabsContent>
      </Tabs>
    </EstadoConsulta>
  )
}
