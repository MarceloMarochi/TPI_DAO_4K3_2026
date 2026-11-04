import { useState } from "react"

import { EstadoConsulta } from "@/components/comunes"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCatalogos } from "@/hooks/useCatalogos"
import { CATALOGOS, GrillaCatalogo } from "./GrillaCatalogo"
import { FormularioIngreso, ImportarCSV, PanelExistencias } from "./PanelesStock"

export function VistaCatalogos() {
  const catalogos = useCatalogos()
  // Cambiar la clave fuerza a las sub-vistas a recargar después de una importación o un ingreso.
  const [version, setVersion] = useState(0)
  const actualizar = () => {
    setVersion((v) => v + 1)
    void catalogos.recargar()
  }

  return (
    <EstadoConsulta cargando={catalogos.cargando && !catalogos.datos} error={catalogos.error}>
      <Tabs defaultValue="productos">
        <TabsList variant="line" className="mb-4 flex-wrap">
          {CATALOGOS.map((c) => <TabsTrigger key={c.tipo} value={c.tipo}>{c.titulo}</TabsTrigger>)}
          <TabsTrigger value="existencias">Existencias y mínimos</TabsTrigger>
          <TabsTrigger value="ingresos">Ingreso al CD</TabsTrigger>
          <TabsTrigger value="importar">Importar CSV</TabsTrigger>
        </TabsList>

        {CATALOGOS.map((c) => (
          <TabsContent key={c.tipo} value={c.tipo}>
            <GrillaCatalogo key={version} config={c} proveedores={catalogos.proveedores} alCambiar={() => void catalogos.recargar()} />
          </TabsContent>
        ))}
        <TabsContent value="existencias">
          <PanelExistencias key={version} opcionesSucursales={catalogos.opcionesSucursales} opcionesProductos={catalogos.opcionesProductos} />
        </TabsContent>
        <TabsContent value="ingresos">
          <FormularioIngreso productos={catalogos.productos} opcionesProductos={catalogos.opcionesProductos}
            opcionesProveedores={catalogos.opcionesProveedores} alRegistrar={actualizar} />
        </TabsContent>
        <TabsContent value="importar">
          <ImportarCSV alImportar={actualizar} />
        </TabsContent>
      </Tabs>
    </EstadoConsulta>
  )
}
