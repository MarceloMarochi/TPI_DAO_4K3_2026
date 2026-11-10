# Sistema de Ventas e Inventario: Centro de Distribución a Locales

TP Integrador 2026 · Tema 3 · Desarrollo de Aplicaciones con Objetos · UTN FRC · **Grupo G-029**

| Legajo | Integrante |
| --- | --- |
| 97366 | Brenna, Santino |
| 85264 | Marochi, Marcelo Gabriel |
| 96977 | Ribotta, Juan Martín |
| 403961 | Rosencovich, Juan |
| 406611 | Vilurrubi, Leonardo Agustin |

Aplicación web para controlar el envío de mercadería desde un Centro de Distribución a varios locales y registrar sus ventas. El stock sólo pasa a disponible en un local cuando el bulto que lo trae queda **Verificado**.

El diseño completo (alcance, modelo de clases, reglas de negocio numeradas, reportes y plan de trabajo) está en [docs/Documento maestro del TP.md](docs/Documento%20maestro%20del%20TP.md).

## Estructura

```
backend/
  app/
    negocio/
      catalogo_stock.py    productos, establecimientos, existencias e ingresos simples
      reposicion.py        órdenes y necesidades
      bultos.py            bultos, contenido e historial
      ventas.py            ventas y detalles históricos
      devoluciones.py      devolución de una línea
      estados.py           State: transiciones sin efectos aislados
      pagos.py             Strategy: efectivo y tarjeta
      servicio_*.py        catálogo, logística, ventas, reportes e importación
      modelos.py           importaciones compatibles de las clases
      sistema.py           fachada que delega en los cinco servicios
    inicializar.py  crea la base y carga los datos de ejemplo
    datos/          esquema SQLite, conexión y DAOs
    api/            adaptador HTTP: rutas FastAPI, esquemas y errores
    main.py         crea la aplicación FastAPI
    presentacion/   ExportadorPDF: reportes y comprobante (ReportLab + Matplotlib)
    config.py       ruta de la base y tasas de los medios de pago
  tests/            pytest
docs/               documento maestro, enunciado, diagrama, presentación
frontend/
  src/
    lib/            cliente HTTP tipado, tipos de la API, formato
    store/          Zustand: local de caja y borrador de venta
    hooks/          consultas y acciones
    components/     componentes comunes y shadcn/ui (components/ui)
    vistas/         catalogos, logistica, caja, reportes
```

## Puesta en marcha del backend

Requiere Python 3.12 o superior. La primera vez se crea el entorno virtual y se instalan las dependencias.

**Windows (PowerShell):**

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
```

> En Windows conviene usar `py` y no `python`: `python` suele abrir el acceso directo de la Microsoft Store ("Python was not found"). Si PowerShell no deja ejecutar `Activate.ps1`, correr una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

**Linux / Mac:**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Con el entorno activado (el prompt muestra `(.venv)`), `python` ya apunta al del entorno y los comandos siguientes funcionan igual en todos los sistemas.

Crear la base `backend/ventas.sqlite3` con los datos de ejemplo de `backend/datos_ejemplo/`:

```bash
python -m app.inicializar --demo
```

Con `--desde-cero` se borra la base existente y se vuelve a crear.

Levantar la API:

```bash
uvicorn app.main:app --reload
```

La documentación interactiva queda en http://localhost:8000/docs. Desde ahí se pueden probar todas las operaciones.

## Puesta en marcha del frontend

Requiere Node.js 20.19 o superior. Con el backend corriendo, en otra terminal:

```bash
cd frontend
npm install
npm run dev
```

Verificación del frontend: `npm test` ejecuta las regresiones de confirmación con Node y TypeScript; `npm run build` comprueba tipos y genera la compilación de producción.

La aplicación queda en http://localhost:5173 (Vite redirige `/api` al backend en el puerto 8000).

> **Windows con Smart App Control:** Tailwind está fijado en la versión 4.3.0 a propósito, porque el binario de la 4.3.4 lo bloquea el control de aplicaciones de Windows y Vite se queda colgado sin mostrar errores. Si `npm run dev` no arranca, ver la sección 11.4 del documento maestro.

## Avance

- [x] Fase 0: estructura del repositorio y entorno
- [x] Fase 1: dominio (modelos, State, Strategy) con tests
- [x] Fase 2: persistencia SQLite y DAOs (`ReportesDAO` se hace en la fase 5)
- [x] Fase 3: `SistemaVentas`, carga CSV y datos de ejemplo
- [x] Fase 4: API FastAPI (32 operaciones; `/docs`)
- [x] Fase 5: reportes R1 a R4, PDF con gráfico y comprobante (41 operaciones en la API)
- [x] Fase 6: frontend React con las cuatro áreas
- [ ] Fase 7: cierre y demo

## Correcciones y reorganización del 09/11/2026

Se mantiene el alcance de la presentación: ingresos simples al CD, efectivo y tarjeta,
una línea por devolución y caja derivada de ventas menos devoluciones. No se adopta TP3.1
ni se modifica el esquema o la base existente.

- El total se distribuye por mayor resto en centavos enteros, con desempate por código de producto.
- Los reintegros se calculan sobre la cantidad acumulada devuelta. Se conservan los registros
  anteriores; los centavos adelantados por el algoritmo viejo se compensan sin reintegros negativos.
- Las cantidades JSON son enteros estrictos: no admiten booleanos, fracciones ni texto. Los CSV
  mantienen su conversión controlada. Los mínimos admiten cero.
- `POST /api/ventas` exige `total_esperado` finito, no negativo y con precisión de centavos.
  Su ausencia o formato inválido devuelve 422; una diferencia contra el servidor devuelve 409.
- `Bulto` aplica juntos la transición, la evidencia y la acreditación. Se conservan State y
  las transacciones; ya no hay métodos públicos para acreditar stock o cambiar estados aisladamente.
- La confirmación conserva una copia inmutable de la solicitud en Zustand. Bloquea cambios,
  descarte y selección de local mientras se resuelve. Una respuesta perdida, ilegible o 5xx
  requiere consulta; un 404 permite reenviar exactamente la misma operación. La recuperación
  compara número, local, medio, total y cantidades. Un número ocupado por otra venta exige una
  acción explícita antes de generar uno nuevo y volver a cotizar.
- El estado pendiente sobrevive al cambio de vista. Al cerrar o recargar se solicita la advertencia
  del navegador; no se agregó persistencia de borradores entre recargas.

Los cinco servicios comparten la conexión de la solicitud y preservan las transacciones completas,
incluida la importación de CSV. Las reglas monetarias permanecen en el dominio y el SQL en los DAOs.
`modelos.py` y `sistema.py` quedan como puntos de acceso pequeños para mantener compatibilidad.

Validación: suite backend con pytest, regresiones frontend con `npm test` y compilación con
`npm run build`. Las pruebas usan datos temporales o en memoria, no `backend/ventas.sqlite3`.
