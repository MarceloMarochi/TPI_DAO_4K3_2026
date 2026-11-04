# Documento maestro: TP Integrador DAO 2026, Tema 3

**Sistema de Ventas e Inventario: Centro de Distribución a Locales** (versión web, "TP 2.0")

**Grupo G-029** · UTN FRC · Desarrollo de Aplicaciones con Objetos

| Legajo | Integrante |
| --- | --- |
| 97366 | Brenna, Santino |
| 85264 | Marochi, Marcelo Gabriel |
| 96977 | Ribotta, Juan Martín |
| 403961 | Rosencovich, Juan |
| 406611 | Vilurrubi, Leonardo Agustin |

Este archivo consolida todo lo que está disperso en la carpeta. Es la **fuente única de verdad** para implementar. Si algo de acá contradice otro archivo, gana este (la sección 13 explica cada contradicción y cómo se resolvió).

---

## Índice

1. [Inventario de archivos y su estado](#1-inventario-de-archivos-y-su-estado)
2. [La consigna en una página](#2-la-consigna-en-una-página)
3. [Matriz de cumplimiento de la consigna](#3-matriz-de-cumplimiento-de-la-consigna)
4. [Alcance: qué entra y qué no](#4-alcance-qué-entra-y-qué-no)
5. [Stack tecnológico](#5-stack-tecnológico)
6. [Arquitectura en capas](#6-arquitectura-en-capas)
7. [Modelo de clases vigente (30 clases)](#7-modelo-de-clases-vigente-30-clases)
8. [Patrones de diseño](#8-patrones-de-diseño)
9. [Reglas de negocio numeradas](#9-reglas-de-negocio-numeradas)
10. [Persistencia](#10-persistencia)
11. [API HTTP e interfaces web](#11-api-http-e-interfaces-web)
12. [Reportes R1 a R4](#12-reportes-r1-a-r4)
13. [Inconsistencias detectadas y resolución](#13-inconsistencias-detectadas-y-resolución)
14. [Pendientes y preguntas abiertas](#14-pendientes-y-preguntas-abiertas)
15. [Plan de implementación](#15-plan-de-implementación)

---

## 1. Inventario de archivos y su estado

| Archivo | Contenido | Estado |
| --- | --- | --- |
| `enunciado ventas.pdf` | Consigna oficial de la cátedra | **Fuente oficial** |
| `Presentacion-grupo (1).docx` | Presentación completa v2.0: objetivos, alcance, UML, arquitectura web, API, reportes | **Vigente**: es el documento más completo y actualizado |
| `2.0.drawio.png` | Diagrama de clases v2.0 (con `AdaptadorAPI`) | **Vigente** |
| `Arquitectura e interfaces.md` | Tecnologías, capas, concurrencia, idempotencia, las 4 pantallas | **Vigente** |
| `Reportes.md` | Fórmulas y criterios de R1 a R4 | **Vigente** |
| `Cambios.md` | Diferencias entre la versión de escritorio y la 2.0 | Vigente (histórico) |
| `README.md` | Índice de la documentación | Parcial: enlaza archivos que **no están en esta carpeta** (ver I-05) |
| `Modelo de Clases Ventas.md` | Catálogo de clases y reglas | **Desactualizado**: versión de escritorio (`VistaPrincipal`, Flet/Tkinter) |
| `modelo_completo.mmd` | Diagrama Mermaid | **Desactualizado**: igual que el anterior |
| `DCL DAO.png` | Diagrama de clases | **Desactualizado**: versión de escritorio |
| `Reglas del modelo.md.pdf` | Reglas del modelo | **Duplicado**: mismo texto que la segunda mitad de `Modelo de Clases Ventas.md` |

---

## 2. La consigna en una página

**Contexto:** un comercio con varios locales se abastece desde un Centro de Distribución (CD). El CD arma bultos, los despacha y los locales los reciben. **Nada ingresa a stock vendible sin verificación.**

**Procesos obligatorios**

1. Administrar sucursales/locales y CD.
2. Administrar productos, categorías, precios, mínimos de existencia y proveedores.
3. Consolidar necesidades de los locales en una orden de reposición al CD (origen y destino).
4. Empaquetar en bultos asignando remito de despacho y precinto de seguridad.
5. Registrar el despacho de los bultos.
6. Registrar la recepción en el local, verificando que el precinto no haya sido violado.
7. Registrar ventas (uno o más productos), cobros con medios de pago, comprobante y devoluciones con impacto en stock y caja.

**Validaciones obligatorias**

- El stock no es *Disponible* en destino hasta que remito y contenedor estén *Verificados*. Precinto roto implica *Rechazado* y no habilita venta.
- Trazabilidad inmutable de estados del bulto: Preparado, Precintado, En tránsito, Recibido, Verificado/Rechazado.
- No vender más que el stock disponible y verificado.
- Sin productos ni proveedores duplicados.
- No aceptar devoluciones que no correspondan a una venta registrada o que incumplan reglas.

**Requisitos de evaluación:** al menos **2 patrones de diseño** y al menos **4 reportes no triviales**. El ciclo de vida del bulto se evalúa críticamente.

**Opcionales (no los tomamos):** órdenes de compra sugeridas, promociones, lotes/vencimientos, clientes frecuentes, inventario físico.

---

## 3. Matriz de cumplimiento de la consigna

| Requisito | Cómo lo cubre el diseño | Dónde se implementa |
| --- | --- | --- |
| P1 Sucursales y CD | `Sucursal` con `es_cd`; exactamente un CD | `modelos.py`, `CatalogoDAO` |
| P2 Productos, categorías, precios, mínimos, proveedores | `Producto` (categoría como texto), `Existencia.minimo`, proveedores como filas código/nombre | `modelos.py`, `CatalogoDAO`, CSV |
| P3 Orden de reposición consolidada | `OrdenReposicion` + `DetalleReposicion`; `agregar_necesidad` suma producto+destino | `modelos.py`, `LogisticaDAO` |
| P4 Bulto con remito y precinto | `Bulto` guarda `remito_numero` y `precinto_numero` únicos | `modelos.py`, `estados.py` |
| P5 Despacho | `Precintado.despachar` pasa a `EnTransito` | `estados.py` |
| P6 Recepción con control de precinto | `EnTransito.recibir(intacto)` pasa a `Recibido` o `Rechazado` | `estados.py` |
| P7 Ventas, cobro, comprobante, devoluciones | `Venta` (Strategy `MedioPago`), `Devolucion`, comprobante PDF | `modelos.py`, `pagos.py`, `ExportadorPDF` |
| V1 Stock disponible sólo tras Verificado | Sólo `Recibido.verificar(conforme=True)` acredita stock en destino | `estados.py`, `SistemaVentas` |
| V2 Trazabilidad inmutable | `CambioEstado` inmutable; tabla sin UPDATE/DELETE (triggers) | `modelos.py`, `schema.sql` |
| V3 No vender sin stock | `Existencia.retirar` valida; transacción antes de leer saldo | `modelos.py`, `SistemaVentas` |
| V4 Sin duplicados | Validación en negocio y `UNIQUE` en SQLite | `SistemaVentas`, `schema.sql` |
| V5 Devoluciones válidas | `Devolucion.validar` comprueba pertenencia y acumulado | `modelos.py`, `VentaDAO` |
| 2 patrones | **State** (bulto) y **Strategy** (medio de pago). DAO como patrón arquitectónico adicional | `estados.py`, `pagos.py`, `datos/` |
| 4 reportes no triviales | R1 Ventas e ingresos, R2 Productos y margen, R3 Existencias y mínimos, R4 Rechazos | `ReportesDAO`, `ExportadorPDF` |

---

## 4. Alcance: qué entra y qué no

### Entra

- Un CD y varios locales; un catálogo compartido.
- Proveedores como **registros simples** (código + nombre), sin clase propia.
- Categoría como **texto** dentro de `Producto`.
- Un proveedor principal por producto.
- `IngresoStock`: entrada simple de compra al CD (sin pedidos de compra ni cuentas a pagar).
- Orden de reposición directa (sin solicitudes previas ni aprobaciones).
- Ciclo completo del bulto con historial inmutable.
- Ventas con Efectivo (descuento) o Tarjeta (recargo); un único cobro por venta.
- Devoluciones de **una línea por registro**.
- 4 reportes con exportación PDF; R1 con gráfico Matplotlib.
- Carga inicial por CSV.

### Clases eliminadas a propósito (se simplificó de 58 a 30)

Compra, DetalleCompra, Proveedor, Categoria, SolicitudReposicion, DetalleSolicitud, RemitoDespacho, Precinto, Recepcion, Cobro, Comprobante, Caja, MovimientoCaja, Inventario, MovimientoInventario. Tampoco hay servicios especializados, DAO por entidad, BaseDAO ni Singleton.

### No entra

ABM por entidad, bajas físicas de datos referenciados, circuito de compras y cuentas a pagar, cancelación o reapertura de bultos, reintegro logístico al origen, lotes y vencimientos, promociones, pagos combinados, cuotas, cuentas corrientes, inventarios físicos, usuarios, roles y autenticación, despliegue público, integraciones bancarias o fiscales.

---

## 5. Stack tecnológico

| Capa | Tecnología | Responsabilidad |
| --- | --- | --- |
| Frontend | React + TypeScript | Pantallas, eventos, formularios, tipos |
| Frontend | shadcn/ui + Tailwind CSS | Componentes y estilos |
| Frontend | Zustand | Sólo estado compartido de UI: local seleccionado y borrador de venta. **No es el patrón State** |
| Frontend | Vite | Servidor de desarrollo y build; proxy de `/api` al backend |
| Backend | FastAPI | Adaptador HTTP: rutas, validación estructural, serialización, OpenAPI |
| Backend | Uvicorn | Servidor ASGI |
| Backend | Python (POO) | Modelos, State, Strategy, `SistemaVentas` |
| Datos | `sqlite3` + SQLite | 4 DAOs con SQL parametrizado y transacciones |
| Reportes | ReportLab + Matplotlib | PDF (`SimpleDocTemplate`, `Paragraph`, `Table`) y gráfico en `BytesIO` |
| Carga | `csv` nativo | `csv.reader`, `with open(..., newline="", encoding="utf-8-sig")`, `next(reader, None)` |
| Contrato | OpenAPI 3.1 | Generado por FastAPI en `/openapi.json` y `/docs` |

> Nota: el docente indicó "frontend libre, backend Python, base de datos libre". El grupo confirmó la versión web (P-03).

---

## 6. Arquitectura en capas

```
Navegador (React)
   │  HTTP/JSON  (PDF como binario)
   ▼
Presentación servidor: AdaptadorAPI (rutas FastAPI + esquemas)   ← Uvicorn
   │
   ▼
Negocio: SistemaVentas (coordina casos de uso y transacciones)
         Modelos + State + Strategy (validaciones y cálculos)
   │
   ▼
Datos: ConexionSQLite + CatalogoDAO, LogisticaDAO, VentaDAO, ReportesDAO
   │
   ▼
SQLite
```

**Reglas de capa (no negociables):**

- React no calcula importes, stock, porcentajes ni estados permitidos: los recibe del servidor.
- `AdaptadorAPI` no tiene SQL, fórmulas ni reglas de stock. Traduce errores a HTTP.
- `SistemaVentas` no tiene SQL ni controles gráficos.
- Todo el SQL vive en los 4 DAOs.
- Las validaciones de negocio se ejecutan aunque la llamada no venga de React.

**Concurrencia y transacciones:**

- Cada solicitud HTTP crea su propia `ConexionSQLite` y su propio `SistemaVentas`. No hay objetos mutables globales ni caché de stock.
- Los DAOs de una misma operación comparten la conexión y **no hacen commit individual**.
- La transacción de escritura se abre **antes** de leer saldos, estados o cantidades devueltas (`BEGIN IMMEDIATE`). Todo se confirma o todo se revierte.

**Idempotencia:** cada alta (venta, devolución, ingreso, orden, bulto) lleva un número único. Si se pierde la respuesta, el frontend consulta por ese número antes de reenviar. `UNIQUE` en la base impide duplicar.

**Cotización:** `POST /api/ventas/cotizacion` calcula sin guardar ni reservar. Al confirmar, el servidor recalcula; si el total difiere del `total_esperado` enviado, responde **409** sin guardar.

---

## 7. Modelo de clases vigente (30 clases)

Composición: 12 de dominio + 7 de State + 3 de Strategy + 8 técnicas. Diagrama de referencia: `2.0.drawio.png`.

**Convenciones POO para todas las clases:**

- Atributos protegidos con prefijo `_`.
- Acceso con `@property`; modificación con setters que validan y lanzan `ValueError`.
- Datos históricos bloqueados después de inicializarse (el setter rechaza cambios).
- Colecciones internas como `list`; la propiedad devuelve **una copia**.
- Ningún objeto modifica atributos protegidos de otro.
- Clases abstractas con `ABC` y `@abstractmethod`.
- Importes con `Decimal`, redondeados a centavos.

### 7.1 Dominio (12)

| Clase | Atributos | Operaciones | Reglas clave |
| --- | --- | --- | --- |
| **Producto** | `codigo`, `nombre`, `categoria: str`, `proveedor_codigo`, `precio: Decimal`, `costo_referencia: Decimal` | — | Código único; nombre y categoría no vacíos; precio y costo > 0 |
| **Sucursal** | `codigo`, `nombre`, `es_cd: bool`, `existencias: list[Existencia]` | `buscar_existencia(codigo)` | Exactamente un CD. `es_cd` valida origen/destino, nunca elige fórmulas |
| **Existencia** | `producto`, `cantidad: int`, `minimo: int` | `ingresar(n)`, `retirar(n)`, `faltante()` | Sólo stock **disponible y habilitado**. Valores ≥ 0 |
| **IngresoStock** | `numero`, `fecha`, `producto`, `proveedor_codigo`, `cantidad`, `costo_unitario` | `importe()` | Un producto por registro; cantidad y costo > 0; proveedor existente; número único. Actualiza `costo_referencia` del producto |
| **OrdenReposicion** | `numero`, `fecha`, `origen: Sucursal`, `detalles: list[DetalleReposicion]`, `cerrada: bool` | `agregar_necesidad(destino, producto, cantidad)`, `validar()`, `cerrar_edicion()` | Origen = CD. Suma cantidades si se repite producto+destino. Se cierra al preparar el primer bulto |
| **DetalleReposicion** | `id`, `destino: Sucursal`, `producto`, `cantidad` | — | Cantidad > 0; destino es un local. Pendiente = cantidad − asignado a bultos |
| **Bulto** | `codigo`, `orden`, `destino`, `remito_numero`, `precinto_numero?`, `precinto_intacto?`, `detalles: list[DetalleBulto]`, `estado: EstadoBulto`, `historial: list[CambioEstado]` | `precintar(numero)`, `despachar()`, `recibir(intacto, motivo)`, `verificar(conforme, motivo)`, `estado_remito()` | **Contexto State.** Un destino, remito único, contenido fijo al guardar. `estado_remito` deriva del estado |
| **DetalleBulto** | `pedido: DetalleReposicion`, `cantidad` | — | Cantidad > 0; destino coincidente; suma asignada ≤ solicitada. Producto = `pedido.producto` |
| **CambioEstado** | `secuencia`, `fecha`, `anterior`, `nuevo`, `motivo` | — | **Inmutable**, incluye el alta en Preparado |
| **Venta** | `numero`, `fecha`, `local`, `detalles: list[DetalleVenta]`, `medio: MedioPago`, `medio_codigo`, `tasa_aplicada`, `total_cobrado`, `comprobante_numero`, `confirmada` | `agregar_detalle(producto, cantidad)`, `subtotal()`, `calcular_total()`, `confirmar()` | **Contexto Strategy.** Un único cobro. Confirmada es inmutable; las correcciones son devoluciones |
| **DetalleVenta** | `id`, `producto`, `cantidad`, `precio_unitario`, `costo_unitario`, `importe_cobrado` | `subtotal()`, `margen()` | Precio y costo históricos. El total se reparte proporcionalmente; el residual de centavos va a la última línea |
| **Devolucion** | `numero`, `fecha`, `venta`, `detalle`, `cantidad`, `apta_reventa`, `motivo`, `importe_reintegrado` | `validar(cantidad_ya_devuelta)`, `calcular_reintegro(importe_ya_devuelto)` | Una línea por registro; acumulado ≤ vendido; reintegro por el medio original; el último reintegro absorbe el residual |

### 7.2 State (7)

`EstadoBulto` (ABC): `nombre()` y `permite_sucesor(nombre)` abstractos. `precintar`, `despachar`, `recibir`, `verificar` lanzan `ValueError` por defecto. Concretos: `Preparado`, `Precintado`, `EnTransito`, `Recibido`, `Verificado`, `Rechazado`. Ver sección 8.1.

### 7.3 Strategy (3)

`MedioPago` (ABC, `codigo`, `calcular_total(base)` abstracto), `Efectivo` (`descuento`), `Tarjeta` (`recargo`). Ver sección 8.2.

### 7.4 Técnicas (8)

| Clase | Responsabilidad | Operaciones |
| --- | --- | --- |
| **SistemaVentas** | Único coordinador de casos de uso y transacciones. Valida proveedores. Una instancia por solicitud | `guardar_catalogo(tipo, datos)`, `registrar_ingreso(datos)`, `crear_orden(necesidades)`, `preparar_bulto(datos)`, `precintar(codigo, numero)`, `despachar(codigo)`, `recibir(codigo, intacto, motivo)`, `verificar(codigo, conforme, motivo)`, `cotizar_venta(datos)`, `confirmar_venta(datos, medio)`, `devolver(datos)`, `importar_csv(ruta)`, `consultar_reporte(nombre, filtros)`, `consultar_catalogo(tipo, filtros)`, `consultar_orden`, `consultar_bulto`, `consultar_venta`, `consultar_devolucion`, `consultar_ingreso`, `configurar_minimo(sucursal, producto, minimo)`, `consultar_medios_pago()`, `consultar_existencias(filtros)` |
| **CatalogoDAO** | Productos, sucursales, proveedores, existencias, ingresos | `guardar_producto`, `guardar_sucursal`, `guardar_proveedor`, `listar_catalogos`, `guardar_existencia`, `insertar_ingreso`, `buscar_ingreso`, `consultar_existencias` |
| **LogisticaDAO** | Órdenes, bultos, historial | `guardar_orden`, `guardar_bulto`, `buscar_bulto`, `registrar_transicion`, `asignado_a_detalle`, `buscar_orden`, `listar_ordenes`, `listar_bultos` |
| **VentaDAO** | Ventas, detalles, devoluciones | `insertar_venta`, `buscar_venta`, `insertar_devolucion`, `acumulado_devuelto`, `buscar_devolucion`, `listar_ventas` |
| **ReportesDAO** | 4 consultas agregadas | `ventas(filtros)`, `productos(filtros)`, `existencias(filtros)`, `rechazos(filtros)` |
| **ConexionSQLite** | Conexión por solicitud y transacción | `transaccion()`, `cerrar()` |
| **AdaptadorAPI** | Frontera HTTP (rutas FastAPI) | `atender_solicitud`, `serializar_respuesta`, `traducir_error`, `descargar_pdf` |
| **ExportadorPDF** | PDF de reportes y comprobantes | `exportar_reporte(datos) -> bytes`, `emitir_comprobante(venta) -> bytes`, `crear_grafico(series) -> BytesIO` |

### 7.4.1 Decisiones tomadas al implementar (fase 1)

- Los estados del bulto se identifican con códigos en mayúsculas: `PREPARADO`, `PRECINTADO`, `EN_TRANSITO`, `RECIBIDO`, `VERIFICADO`, `RECHAZADO`. El frontend los traduce a etiquetas.
- **Crear un `Bulto` equivale a prepararlo:** el constructor valida el contenido, descuenta el CD (primero verifica todas las líneas, para no dejar descuentos a medias) y cierra la orden. Para leer un bulto de la base se usa `Bulto.restaurar(...)`, que no repite esos efectos.
- `EstadoBulto` agrega `acciones_permitidas()` y `estado_remito()`, redefinidos por cada estado concreto: así la API informa qué botones mostrar sin `if` por tipo.
- Sólo `Recibido.verificar(conforme=True)` llama a `Bulto.acreditar_destino()`, que además se niega a ejecutarse si el estado actual no admite pasar a `VERIFICADO`.
- `IngresoStock.aplicar(cd)` suma el stock al CD y actualiza el costo de referencia.
- `Venta.agregar_detalle` ya controla el disponible del local (para avisar temprano); `confirmar()` lo vuelve a controlar antes de descontar. El comprobante por defecto es `CI-<número de venta>`.
- `Devolucion.calcular_reintegro(importe_ya_devuelto, cantidad_ya_devuelta)` recibe también la cantidad, para saber si es la última devolución de la línea (la que absorbe el residuo). `Devolucion.confirmar(...)` valida, fija el reintegro y reingresa el stock si es apta.
- `CambioEstado` es inmutable de verdad: cualquier asignación posterior a su creación lanza `AttributeError`.

### 7.4.2 Decisiones tomadas al implementar (fase 3)

- **Errores de negocio** (`negocio/errores.py`), todos subclases de `ValueError`:
  - `ValueError` común: dato inválido → HTTP 422.
  - `NoEncontrado`: código o número inexistente → HTTP 404.
  - `Conflicto`: la regla depende del estado actual (stock insuficiente, transición no permitida, duplicado, documento ya confirmado, total cambiado) → HTTP 409.
  - `ErrorImportacion`: lleva la lista de errores por fila (`fila`, `campo`, `mensaje`).
- Convención de mensajes: los errores de un campo empiezan con su nombre en minúscula (`"precio: debe ser mayor que cero"`), lo que permite informar el campo en la importación CSV.
- `SistemaVentas` guarda productos, sucursales y proveedores como **diccionarios por código** (el diagrama decía `list`): las búsquedas por código son directas.
- Toda operación de escritura sigue el mismo patrón: abrir la transacción, recargar el catálogo dentro de ella, operar con los objetos del dominio, guardar con los DAOs y confirmar.
- `guardar_catalogo(tipo, datos, alta=True)`: con `alta=True` un código existente es `Conflicto`; con `alta=False` (edición) un código inexistente es `NoEncontrado`. Un establecimiento no puede cambiar de local a CD ni al revés.
- Las entradas y salidas son diccionarios simples; los importes viajan como `Decimal` y las fechas como `datetime`. La API sólo tiene que serializarlos.
- Las cantidades aceptan entero o texto numérico, porque los CSV llegan como texto. `es_cd` y `apta_reventa` aceptan `sí/no`, `true/false` o `1/0`.
- Importación CSV: tipos `proveedores`, `sucursales`, `productos`, `ingresos` y `minimos`. Acepta coma o punto y coma como separador (Excel en español usa punto y coma). Valida todas las filas y, si alguna falla, revierte todo e informa cada error.
- Datos de ejemplo en `backend/datos_ejemplo/`: 3 proveedores, el CD y 3 locales, 10 productos, ingresos al CD y mínimos. Se cargan con `python -m app.inicializar --demo`.

### 7.5 Relaciones principales

- **Composición:** Sucursal ◆ Existencia · OrdenReposicion ◆ DetalleReposicion · Bulto ◆ DetalleBulto · Bulto ◆ CambioEstado · Venta ◆ DetalleVenta.
- **Agregación:** SistemaVentas ◇ Producto, Sucursal (cargados en la solicitud).
- **Herencia:** 6 estados → EstadoBulto; Efectivo, Tarjeta → MedioPago.
- **Asociación:** Existencia→Producto; OrdenReposicion→Sucursal (origen CD); DetalleReposicion→Sucursal (destino), Producto; Bulto→OrdenReposicion, Sucursal (destino), EstadoBulto; DetalleBulto→DetalleReposicion; Venta→Sucursal (local), MedioPago; DetalleVenta→Producto; Devolucion→Venta, DetalleVenta.
- **Dependencia:** SistemaVentas → 4 DAOs y ConexionSQLite; DAOs → ConexionSQLite; AdaptadorAPI → SistemaVentas, ExportadorPDF; ExportadorPDF → Venta.
- Las multiplicidades `1..*` aplican a objetos guardados: no se persisten órdenes, bultos ni ventas sin detalles.

---

## 8. Patrones de diseño

### 8.1 State: ciclo de vida del bulto

| Estado actual | Operación | Estado siguiente | Efecto en stock |
| --- | --- | --- | --- |
| (alta) | Preparar con orden, contenido y stock suficiente | **Preparado** | **Descuenta** disponible del CD (única vez) |
| Preparado | Precintar con número único | **Precintado** | — |
| Precintado | Despachar | **En tránsito** | — |
| En tránsito | Recibir con precinto intacto | **Recibido** | — |
| En tránsito | Recibir con precinto roto (motivo obligatorio) | **Rechazado** | — (queda fuera de venta) |
| Recibido | Verificar conforme | **Verificado** | **Acredita** disponible en el local |
| Recibido | Verificar no conforme (motivo obligatorio) | **Rechazado** | — (queda fuera de venta) |
| Verificado / Rechazado | Cualquier operación | `ValueError` | — |

- `Bulto` delega cada operación en `self._estado`. **Sin `if/elif` por tipo de estado.**
- Cada transición agrega exactamente un `CambioEstado`. El setter de estado valida con `permite_sucesor`.
- Repetir una verificación falla y no vuelve a acreditar stock.
- Rechazado no devuelve unidades al CD ni se considera pérdida definitiva.

### 8.2 Strategy: medio de pago

- `Venta.calcular_total()` → `self._medio.calcular_total(self.subtotal())`.
- `Efectivo`: `base × (1 − descuento)`, con `0 ≤ descuento < 1`.
- `Tarjeta`: `base × (1 + recargo)`, con `recargo ≥ 0`.
- Las tasas se configuran en el servidor (validadas al iniciar); cada venta guarda la tasa aplicada.
- En la base se guarda el código del medio y se reconstruye con un registro de clases (`{"EFECTIVO": Efectivo, "TARJETA": Tarjeta}`). Lo mismo para los estados.

---

## 9. Reglas de negocio numeradas

Sirven para escribir un test por regla.

**Catálogo**

- RN-01 Códigos de producto, sucursal y proveedor únicos (negocio + `UNIQUE`).
- RN-02 Los códigos referenciados no se modifican ni se eliminan.
- RN-03 Existe exactamente un CD.
- RN-04 Una existencia por producto y establecimiento; cantidad y mínimo ≥ 0.
- RN-05 El disponible no se edita a mano: sólo cambia por ingreso, preparación, verificación, venta o devolución apta. El mínimo sí se edita.

**Abastecimiento**

- RN-06 `IngresoStock` sólo al CD, con proveedor existente, cantidad > 0, costo > 0 y número único.
- RN-07 Un ingreso actualiza el `costo_referencia` para ventas futuras, sin tocar operaciones anteriores.

**Reposición y logística**

- RN-08 La orden tiene origen CD y destinos que son locales; al menos un detalle.
- RN-09 Necesidades repetidas (producto + destino) se suman en una misma línea.
- RN-10 La orden se cierra al preparar su primer bulto.
- RN-11 Un bulto tiene un solo destino; sus detalles pertenecen a esa orden y ese destino.
- RN-12 Lo asignado a bultos para un detalle no supera lo solicitado.
- RN-13 Al preparar, el CD debe tener stock suficiente; se descuenta una única vez.
- RN-14 Remito y precinto únicos.
- RN-15 Transiciones según la tabla 8.1; cualquier otra lanza `ValueError` (HTTP 409).
- RN-16 Rechazo (por precinto o por verificación no conforme) exige motivo.
- RN-17 Sólo Verificado acredita stock en destino.
- RN-18 El historial no admite UPDATE ni DELETE.

**Ventas y devoluciones**

- RN-19 Venta con al menos una línea, cantidades > 0, en un local (no CD).
- RN-20 No vender más que el disponible del local.
- RN-21 La venta guarda precio, costo, tasa e importes históricos; confirmada es inmutable.
- RN-22 El total cobrado se distribuye proporcionalmente; el residual de centavos va a la última línea.
- RN-23 Confirmar recalcula; si difiere del total esperado, 409 sin guardar.
- RN-24 La devolución refiere a una venta existente y a una línea de esa venta.
- RN-25 Cantidad devuelta acumulada ≤ cantidad vendida.
- RN-26 Reintegro por el medio original con el importe histórico; el último reintegro absorbe el residual; acumulado ≤ cobrado.
- RN-27 Sólo lo apto para reventa vuelve al disponible; lo no apto queda registrado fuera de venta.

**Carga CSV**

- RN-28 Se valida todo el archivo (encabezado, filas, duplicados, referencias) antes de confirmar; ante error se informa fila y campo y no se importa nada.
- RN-29 El stock inicial entra como ingresos al CD; nunca se crea disponible en locales por CSV.

---

## 10. Persistencia

**Tablas (13):** `proveedores`, `productos`, `sucursales`, `existencias`, `ingresos_stock`, `ordenes`, `detalles_reposicion`, `bultos`, `detalles_bulto`, `historial_estados`, `ventas`, `detalles_venta`, `devoluciones`.

- Claves foráneas activas (`PRAGMA foreign_keys = ON`).
- `UNIQUE` en códigos y números de documento; `UNIQUE(producto, sucursal)` en existencias.
- `CHECK` de cantidades no negativas.
- Triggers que bloquean UPDATE y DELETE en `historial_estados`.
- Estado del bulto y medio de pago como códigos de texto.
- Fechas asignadas por el servidor, con zona horaria (America/Buenos_Aires).
- **Importes guardados como enteros en centavos** (`precio_centavos`, `total_cobrado_centavos`, etc.) para que los `SUM` de los reportes sean exactos. Las tasas se guardan como texto decimal (`'0.10'`).
- Fechas como texto ISO con microsegundos y zona (`2026-11-04T10:15:00.000000-03:00`): tienen ancho fijo y se pueden comparar como texto en los filtros por período.
- Triggers que bloquean UPDATE y DELETE también en `ingresos_stock`, `ventas`, `detalles_venta`, `devoluciones` y `detalles_bulto`.
- Índice único parcial `sucursales(es_cd) WHERE es_cd = 1`: la base garantiza un único CD.

### 10.1 Decisiones tomadas al implementar (fase 2)

- `ConexionSQLite` abre la conexión en modo autocommit y controla las transacciones a mano: `with conexion.transaccion():` ejecuta `BEGIN IMMEDIATE`, y al salir hace `COMMIT`, o `ROLLBACK` si hubo una excepción. No admite transacciones anidadas. Los DAOs nunca hacen commit.
- Por solicitud se carga el catálogo completo con `CatalogoDAO.cargar_catalogo()`, que devuelve `productos` y `sucursales` (con sus existencias) como diccionarios por código. Los métodos `buscar_*` de los DAOs reciben esos diccionarios para reconstruir los objetos sobre **las mismas instancias**. Así, cuando un bulto acredita stock en un local, se modifica la misma `Sucursal` que después se guarda.
- `CatalogoDAO.guardar_existencias(sucursal)` reemplaza a `guardar_existencia(existencia)`: guarda todas las existencias del establecimiento con un *upsert* (una `Existencia` no conoce su sucursal).
- `LogisticaDAO.guardar_bulto(bulto)` inserta el bulto si es nuevo o actualiza su estado, y siempre agrega al historial sólo los cambios con secuencia mayor a la guardada (`registrar_transicion`).
- Consultas agregadas para la interfaz: `LogisticaDAO.pendientes_de_orden`, `listar_ordenes`, `listar_bultos`; `VentaDAO.listar_ventas`; `CatalogoDAO.consultar_existencias`, `listar_catalogos`.
- `VentaDAO.acumulado_devuelto(detalle_id)` devuelve `(cantidad, importe)`.
- Una violación de `UNIQUE` o de clave foránea llega como `sqlite3.IntegrityError`; la API la traducirá a 409.

---

## 11. API HTTP e interfaces web

### 11.1 Convenciones

- Prefijo `/api`. Importes como cadenas decimales con 2 posiciones. Fechas ISO con zona horaria.
- Errores con formato uniforme `{codigo, mensaje, detalles}`.
- **422** dato inválido · **404** recurso inexistente · **409** conflicto de stock, unicidad, transición o cotización.
- La API informa las **acciones permitidas** de cada bulto; React no reimplementa State.

### 11.2 Endpoints conocidos

El contrato completo (40 operaciones, `API/openapi.json`) no está en esta carpeta (ver P-02). Los documentados son:

| Método y ruta | Finalidad |
| --- | --- |
| `GET /api/productos` | Consultar catálogo |
| `POST /api/ordenes` | Consolidar necesidades |
| `POST /api/bultos` | Preparar bulto y descontar el CD |
| `POST /api/bultos/{codigo}/verificar` | Verificar (acredita sólo si corresponde) |
| `POST /api/ventas/cotizacion` | Calcular sin guardar |
| `POST /api/ventas` | Confirmar venta |
| `POST /api/devoluciones` | Registrar devolución |
| `GET /api/reportes/ventas/pdf` | PDF de R1 con gráfico |

Los demás se derivan directamente de las operaciones de `SistemaVentas` (sección 7.4).

### 11.2.1 Endpoints implementados (fase 4)

El contrato vivo está en `http://localhost:8000/docs` (Swagger) y `/openapi.json`. Hay 32 operaciones; los reportes y los PDF se suman en la fase 5.

| Área | Operaciones |
| --- | --- |
| Catálogos y stock | `GET/POST /api/proveedores`, `PUT /api/proveedores/{codigo}` · lo mismo para `/api/sucursales` y `/api/productos` · `GET /api/existencias?sucursal=&producto=` · `PUT /api/existencias/{sucursal}/{producto}/minimo` · `POST /api/ingresos`, `GET /api/ingresos/{numero}` · `POST /api/importaciones/{tipo}` (multipart, campo `archivo`) |
| Logística | `GET /api/ordenes?pendientes=`, `POST /api/ordenes`, `GET /api/ordenes/{numero}` · `GET /api/bultos?estado=&destino=`, `POST /api/bultos`, `GET /api/bultos/{codigo}` · `POST /api/bultos/{codigo}/precintar`, `/despachar`, `/recibir`, `/verificar` |
| Caja | `GET /api/medios-pago` · `POST /api/ventas/cotizacion` · `POST /api/ventas`, `GET /api/ventas?local=`, `GET /api/ventas/{numero}` · `POST /api/devoluciones`, `GET /api/devoluciones/{numero}` |
| General | `GET /api/salud` |

Decisiones:
- **Organización:** `app/api/adaptador.py` cumple el papel de `AdaptadorAPI`: la dependencia `obtener_sistema` crea una conexión y un `SistemaVentas` por solicitud y los cierra al terminar, y los manejadores traducen los errores. Las rutas están en `rutas_catalogo.py`, `rutas_logistica.py` y `rutas_caja.py`, y los esquemas Pydantic en `esquemas.py`.
- **Errores** con formato `{codigo, mensaje, detalles}`: `DATO_INVALIDO` (422), `IMPORTACION_INVALIDA` (422, con fila y campo), `NO_ENCONTRADO` (404) y `CONFLICTO` (409). Un `sqlite3.IntegrityError` también se responde como 409.
- **Esquemas:** los de entrada rechazan campos desconocidos (`extra="forbid"`). Sólo validan la forma del mensaje; los valores los valida el dominio.
- **Alta y edición:** el alta es `POST` con el código en el cuerpo. La edición es `PUT /{codigo}`: el código va sólo en la ruta, así que no se puede cambiar.
- **Importación CSV:** el archivo se guarda en `backend/tmp/` con un nombre generado (nunca el nombre del usuario), se importa y se borra. Límite de 2 MB.
- **Inicio:** al arrancar, el servidor crea las tablas si no existen y valida las tasas (si están mal configuradas, no arranca).
- **CORS:** habilitado sólo para el servidor de desarrollo de Vite (`localhost:5173`).

### 11.3 Las 4 pantallas

| Área | Qué hace |
| --- | --- |
| **Catálogos y stock** | Grilla reutilizable para productos, sucursales y proveedores (alta, edición, búsqueda; sin bajas). Panel de existencias (sólo el mínimo es editable). Formulario de ingreso al CD. Importación CSV con errores por fila |
| **Logística** | Alta y consulta de órdenes con pendientes. Preparación de bulto (orden + destino + líneas, código y remito). Tabla de bultos filtrable por estado y destino; detalle con contenido e historial. Botones Precintar, Despachar, Recibir y Verificar según las acciones permitidas |
| **Caja** | Local, buscador de productos, cantidades, medio de pago; cotización del servidor; confirmación; descarga del comprobante PDF. Devoluciones: buscar venta, elegir línea, cantidad, aptitud y motivo |
| **Reportes** | Selector R1 a R4, filtros, tabla con totales y descarga PDF con los mismos filtros |

Comportamiento común: estados de carga, vacío, éxito y error; botón deshabilitado mientras hay una solicitud pendiente; cambiar de local con un borrador pide confirmación.

### 11.4 Implementación del frontend (fase 6)

**Stack instalado:** Vite 8, React 19, TypeScript 5.9, Tailwind CSS 4.3.0 (versión fija, ver la nota de Windows), shadcn/ui 4 (estilo `base-nova`, sobre **Base UI** en lugar de Radix) y Zustand 5. En desarrollo, Vite redirige `/api` a `http://127.0.0.1:8000`.

**Organización (`frontend/src/`):**

| Carpeta o archivo | Contenido |
| --- | --- |
| `lib/tipos.ts` | Tipos TypeScript que reflejan los esquemas de la API |
| `lib/api.ts` | Cliente HTTP tipado. Distingue `ErrorApi` (el servidor respondió 422, 404 o 409) de `ErrorRed` (no hubo respuesta: la operación pudo haberse registrado) |
| `lib/formato.ts` | Importes y fechas en formato argentino, etiquetas de estados y medios, generador de números de documento |
| `store/contexto.ts` | Zustand: local de caja y borrador de venta (`numero`, `medio`, `items` y `version`) |
| `hooks/` | `useConsulta` (carga, error y recarga), `useAccion` (escrituras con `pendiente`), `useCatalogos` |
| `components/comunes.tsx` | `Seccion`, `MensajeError` (con errores por fila), `EstadoConsulta`, `Campo`, `Seleccion`, `BadgeEstado` |
| `components/ui/` | Componentes de shadcn/ui generados con su CLI |
| `vistas/catalogos/` | Grilla reutilizable para los tres catálogos, existencias con mínimo editable, ingreso al CD, importación CSV |
| `vistas/logistica/` | Nueva orden con varias líneas, órdenes con pendientes, preparación de bulto, seguimiento con historial y acciones |
| `vistas/caja/` | Venta (cotizar, confirmar, comprobante) y devoluciones |
| `vistas/reportes/` | R1 a R4 con filtros, totales, barras de R1, motivos de R4 y descarga del PDF |

**Decisiones:**
- **Números de documento (P-05):** el frontend los genera al iniciar cada borrador (`V-AAMMDD-HHMMSS-XX`, y lo mismo para `O`, `B`, `R`, `ING` y `D`) y se pueden editar. El de una venta se conserva hasta conocer el resultado.
- **Respuesta perdida:** si la confirmación de una venta no recibe respuesta, el botón se bloquea y aparece "Consultar estado", que busca la venta por **el mismo número**. Si existe, se da por confirmada; si da 404, se puede reintentar con ese número.
- **Cotización vencida:** cada edición del borrador incrementa `version`. Una cotización sólo vale para la versión con la que se pidió; si no coincide, "Confirmar" queda deshabilitado. Al confirmar se envía `total_esperado`, y si el servidor responde 409 hay que volver a cotizar.
- **Botones del bulto:** salen de `acciones_permitidas`, que informa el servidor. El frontend no reimplementa el patrón State. Recibir y verificar piden el motivo cuando el resultado es negativo.
- **Sin cálculos en el navegador:** el frontend no suma importes ni stock. Totales, ajustes, reintegros, faltantes y porcentajes llegan del servidor; las barras de R1 sólo escalan los valores recibidos.
- **Cambio de local:** con un borrador cargado, cambiar de local pide confirmación y descarta la venta en preparación.

**Nota para Windows (Smart App Control):** el binario nativo de Tailwind 4.3.4 (`@tailwindcss/oxide-win32-x64-msvc`) fue bloqueado por *"Una directiva de Control de aplicaciones bloqueó este archivo"*. Tailwind cae entonces en su variante WebAssembly, que con Node 26 se cuelga, y `vite` / `npm run build` quedan en un bucle sin mostrar nada. Las versiones anteriores, con más reputación, sí cargan: por eso `tailwindcss` y `@tailwindcss/vite` quedaron fijas en **4.3.0** (sin `^`). Si se actualiza Tailwind, hay que probar primero que el binario cargue con `node -e "require('@tailwindcss/oxide-win32-x64-msvc')"`.

**Verificación:** se recorrió el flujo completo desde el navegador: orden → bulto → precintar → despachar → recibir (el stock del local sigue en 0) → verificar (pasa a 20) → venta con cotización vencida y recotizada → comprobante PDF → devolución no apta → R1 a R4 y PDF. Los importes coincidieron con los del backend y no hubo errores en la consola.

---

## 12. Reportes R1 a R4

**Criterios comunes:** `Decimal`; período "desde/hasta" inclusivo en America/Buenos_Aires; sólo operaciones confirmadas; período invertido devuelve 422; **ventas y devoluciones se agregan por separado antes de unirlas** (para no duplicar importes); JSON y PDF incluyen filtros y fecha de generación.

| Reporte | Filtros | Agrupa por | Indicadores y fórmulas |
| --- | --- | --- | --- |
| **R1 Ventas e ingresos** | desde, hasta, local?, medio? | local × medio | cantidad de ventas, cobrado, reintegrado, **neto = cobrado − reintegrado**. Cada flujo usa su propia fecha. **Gráfico de barras de neto por local** (Matplotlib → BytesIO → PDF) |
| **R2 Productos y margen** | desde, hasta, local? | producto | unidades netas = vendidas − devueltas; importe neto = cobrado − reintegrado; costo neto = Σ vendida×costo hist − Σ devuelta×costo hist; **margen = importe neto − costo neto**. Orden: unidades netas desc, margen desc, código asc. Devueltas aptas y no aptas por separado |
| **R3 Existencias y mínimos** | establecimiento?, producto? (foto actual) | producto × establecimiento | disponible, mínimo, **faltante = max(0, mínimo − disponible)**; CD: comprometido (Preparado + Precintado); local: pendiente de despacho, en tránsito, recibido sin verificar, rechazado; devoluciones no aptas |
| **R4 Rechazos** | desde, hasta, destino? | destino; y destino × motivo | verificados, rechazados, finalizados = V + R, **% = R / finalizados × 100** (null si 0, "sin datos"); unidades rechazadas. % global con totales, no promediando |

**Ejemplos para tests:**

- R1: Centro, efectivo cobra 180000 y reintegra 10000, neto 170000; tarjeta cobra 165000 y reintegra 5000, neto 160000; el gráfico muestra 330000.
- R2: vende 10 a 1000 con costo 600 y devuelve 2: unidades 8, importe 8000, costo 4800, margen 3200.
- R3: disponible 4, mínimo 10, 8 en tránsito: faltante 6 (el tránsito se muestra aparte).
- R4: 18 verificados y 2 rechazados: 20 finalizados, 10.00 %.

### 12.1 Implementación (fase 5)

- **`ReportesDAO`** (`datos/reportes_dao.py`) tiene una consulta SQL por reporte, más `rechazos_detalle` para los motivos. Sólo agrupa y suma: ventas y devoluciones se agregan en CTE separadas y después se unen por clave, así ningún cobro se multiplica por sus devoluciones.
- **`SistemaVentas.consultar_reporte(nombre, filtros)`** valida el período y calcula las fórmulas (neto, unidades netas, margen, faltante, porcentaje), los totales, el ranking y la serie del gráfico. Devuelve `{reporte, titulo, generado, filtros, filas, totales}`; R1 agrega `grafico` y R4 agrega `motivos`. El JSON y el PDF salen de este mismo resultado.
- **Período:** `desde` y `hasta` son fechas (`AAAA-MM-DD`) inclusivas en hora de Buenos Aires. Un período invertido o incompleto da 422.
- **R3** cuenta las unidades según el estado **actual** de cada bulto (no recorre el historial), así ninguna unidad se cuenta dos veces. Filtro adicional `solo_bajo_minimo`.
- **R4** normaliza los motivos (espacios y mayúsculas) antes de agruparlos: "Precinto roto" y "  precinto ROTO " son el mismo motivo.
- **`ExportadorPDF`** (`presentacion/exportador_pdf.py`):
  - `exportar_reporte(datos) -> bytes` arma título, fecha de generación, filtros, tabla con fila de totales y definiciones. R1 suma el gráfico de barras de Matplotlib (en `BytesIO` con `seek(0)`; los negativos se dibujan en rojo). R4 suma la tabla por motivo. Si no hay datos, escribe "Sin movimientos" y no dibuja barras.
  - `emitir_comprobante(venta) -> bytes` arma el comprobante interno con subtotal, descuento o recargo y total.
  - Importes en formato argentino (`$ 1.234,56`, `-$ 3.450,00`).
- **Endpoints nuevos** (9; la API llega a 41 operaciones): `GET /api/reportes/{ventas|productos|existencias|rechazos}` y su variante `/pdf`, y `GET /api/ventas/{numero}/comprobante`.
- **Tests:** los cuatro ejemplos de esta sección dan los valores esperados. Además se prueba que una devolución de una venta anterior cuente en el período del reintegro, que varias devoluciones no dupliquen lo cobrado, que lo recibido sin verificar no sea disponible y que un local sin finalizados quede "sin datos". Esto cubre los criterios de aceptación de `Reportes.md`.

**Reporte extra posible:** "tiempo promedio de tránsito CD→local" (sugerido por el enunciado). Es fácil de agregar porque el historial tiene las fechas de despacho y recepción.

---

## 13. Inconsistencias detectadas y resolución

| ID | Inconsistencia | Resolución |
| --- | --- | --- |
| I-01 | `Modelo de Clases Ventas.md`, `modelo_completo.mmd` y `DCL DAO.png` describen la versión de escritorio (`VistaPrincipal`, Flet/Tkinter, "una ventana con cuatro pestañas") | Rige la v2.0 (docx + `2.0.drawio.png`) con `AdaptadorAPI`. Hay que actualizar el `.md` y el `.mmd` |
| I-02 | `recibir(codigo, intacto)` frente a `recibir(codigo, intacto, motivo)` | Con `motivo`: lo exige el rechazo por precinto roto |
| I-03 | `ExportadorPDF.exportar_reporte(datos, ruta)` frente a `exportar_reporte(datos) -> bytes` | `bytes`: se descarga por HTTP |
| I-04 | `SistemaVentas` y los DAOs tienen más operaciones de consulta en la v2.0 | Rige la lista de la v2.0 (sección 7.4) |
| I-05 | El README enlaza `Diseno UML/` (visor HTML, 6 vistas `.mmd/.svg/.png`), `API/Contrato API.md`, `API/openapi.json` y `Reglas del modelo.md`, que no están en esta carpeta | Pedir esos archivos al grupo (P-02). Si no aparecen, FastAPI genera el OpenAPI desde el código |
| I-06 | `Reglas del modelo.md.pdf` duplica la segunda mitad de `Modelo de Clases Ventas.md` | Se toma una sola fuente (este documento) |
| I-07 | El README enlaza `Presentacion-grupo.docx`, pero el archivo se llama `Presentacion-grupo (1).docx` | Renombrar al subir al repo |
| I-08 | El primer `CambioEstado` (alta en Preparado) no define su valor `anterior` | Usar `anterior = None` (en la base, `NULL`) |
| I-09 | El enunciado sugiere el reporte de tiempo de tránsito, que no está entre R1 a R4 | No es obligatorio; queda como reporte extra opcional |

---

## 14. Pendientes y preguntas abiertas

| ID | Tema | Estado |
| --- | --- | --- |
| P-01 | Número de grupo e integrantes | **Resuelto:** G-029, ver encabezado |
| P-02 | Carpetas `Diseno UML/` y `API/` | **Resuelto:** no se usan. FastAPI genera el OpenAPI desde el código (`/docs`, `/openapi.json`); los diagramas se actualizan al cierre |
| P-03 | Aceptación de la versión web (React + FastAPI) | **Resuelto:** confirmado, se hace web. La versión de escritorio queda descartada |
| P-04 | Tasas: Efectivo con 10 % de descuento y Tarjeta con 10 % de recargo | **Provisorio:** cargadas en `backend/app/config.py` con una marca `TODO(grupo)` para definirlas |
| P-05 | Formato de numeración de documentos (por ejemplo `V-000123`): ¿servidor o cliente? | Abierto. Por ahora el número lo envía quien crea el documento y el servidor valida que sea único |
| P-06 | Versión de Python común del grupo | Abierto. El código exige ≥ 3.12 (local: 3.14.6) |
| P-07 | Repo de GitHub | El código vive en `sistema-ventas/`; Marcelo lo conecta y hace el push |

---

## 15. Plan de implementación

### 15.1 Estructura del repositorio propuesta

```
<repo>/
├── README.md                  ← cómo instalar, correr y probar
├── docs/                      ← este documento, diagramas, enunciado
├── backend/
│   ├── pyproject.toml         ← dependencias (fastapi, uvicorn, reportlab, matplotlib, pytest)
│   ├── app/
│   │   ├── main.py            ← crea la app FastAPI
│   │   ├── config.py          ← ruta de la base de datos y tasas
│   │   ├── api/               ← AdaptadorAPI: rutas y esquemas Pydantic por área
│   │   ├── negocio/
│   │   │   ├── modelos.py     ← 12 clases de dominio
│   │   │   ├── estados.py     ← State
│   │   │   ├── pagos.py       ← Strategy
│   │   │   └── sistema.py     ← SistemaVentas
│   │   ├── datos/
│   │   │   ├── schema.sql
│   │   │   ├── conexion.py
│   │   │   ├── catalogo_dao.py
│   │   │   ├── logistica_dao.py
│   │   │   ├── venta_dao.py
│   │   │   ├── reportes_dao.py
│   │   │   └── carga_csv.py
│   │   └── presentacion/
│   │       └── exportador_pdf.py
│   ├── datos_ejemplo/         ← CSV de proveedores, sucursales, productos, ingresos
│   └── tests/                 ← pytest: un test por regla RN-xx
└── frontend/                  ← Vite + React + TS + Tailwind + shadcn/ui + Zustand
```

### 15.2 Fases

Cada fase termina con tests en verde y un commit (o PR).

| Fase | Entregable | Criterio de terminado |
| --- | --- | --- |
| **0. Setup** | Repo, estructura, `pyproject`, pytest, `.gitignore`, README básico, docs | `pytest` corre; el repo está en GitHub |
| **1. Dominio** | `modelos.py`, `estados.py`, `pagos.py` **sin base de datos** | Tests de RN-04, 08 a 17 y 19 a 27 en memoria; ciclo completo del bulto probado |
| **2. Persistencia** | `schema.sql`, `ConexionSQLite`, `CatalogoDAO`, `LogisticaDAO`, `VentaDAO` | Tests con SQLite en memoria: guardar, reconstruir objetos, triggers del historial, rollback |
| **3. Casos de uso** | `SistemaVentas` + `carga_csv.py` + datos de ejemplo | Flujo completo probado: ingreso → orden → bulto → verificado → venta → devolución |
| **4. API** | Rutas FastAPI y traducción de errores 422, 404 y 409 | `/docs` funciona; tests con `TestClient` |
| **5. Reportes** | `ReportesDAO` (R1 a R4) + `ExportadorPDF` + gráfico | Los ejemplos de la sección 12 dan los valores esperados; los PDF se descargan |
| **6. Frontend** | Las 4 áreas | Recorrido completo desde el navegador |
| **7. Cierre** | Datos de demo, README final, diagramas actualizados, presentación | Demo de punta a punta |

**Por qué este orden:** las fases 1 a 3 son el núcleo que se evalúa (POO, State, Strategy, DAO) y no dependen del frontend. Se pueden probar con pytest sin levantar ningún servidor.

**Reparto sugerido para 3 o 4 personas** (después de la fase 1, que conviene hacer juntos):

- Logística: bultos, órdenes y R3/R4.
- Ventas: ventas, devoluciones y R1/R2.
- Catálogo, CSV y API.
- Frontend (a partir de la fase 4).
