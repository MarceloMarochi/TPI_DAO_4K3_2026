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
    negocio/        modelos, State (estados.py), Strategy (pagos.py),
                    SistemaVentas (sistema.py), errores
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
