-- Esquema SQLite del Sistema de Ventas e Inventario.
-- Convenciones:
--   * Importes en centavos (INTEGER) para sumar sin errores de redondeo.
--   * Tasas como texto decimal ('0.10').
--   * Fechas como texto ISO 8601 con zona horaria y microsegundos (ancho fijo,
--     comparables como texto): '2026-11-04T10:15:00.000000-03:00'.
--   * Los documentos confirmados (ingresos, ventas, devoluciones) y el historial
--     de estados no admiten UPDATE ni DELETE: lo impiden los triggers.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Catálogo y stock
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS proveedores (
    codigo  TEXT PRIMARY KEY,
    nombre  TEXT NOT NULL CHECK (trim(nombre) <> '')
);

CREATE TABLE IF NOT EXISTS sucursales (
    codigo  TEXT PRIMARY KEY,
    nombre  TEXT NOT NULL CHECK (trim(nombre) <> ''),
    es_cd   INTEGER NOT NULL CHECK (es_cd IN (0, 1))
);

-- Exactamente un Centro de Distribución (RN-03).
CREATE UNIQUE INDEX IF NOT EXISTS ux_sucursales_un_solo_cd ON sucursales (es_cd) WHERE es_cd = 1;

CREATE TABLE IF NOT EXISTS productos (
    codigo                     TEXT PRIMARY KEY,
    nombre                     TEXT NOT NULL CHECK (trim(nombre) <> ''),
    categoria                  TEXT NOT NULL CHECK (trim(categoria) <> ''),
    proveedor_codigo           TEXT NOT NULL REFERENCES proveedores (codigo),
    precio_centavos            INTEGER NOT NULL CHECK (precio_centavos > 0),
    costo_referencia_centavos  INTEGER NOT NULL CHECK (costo_referencia_centavos > 0)
);

CREATE TABLE IF NOT EXISTS existencias (
    sucursal_codigo  TEXT NOT NULL REFERENCES sucursales (codigo),
    producto_codigo  TEXT NOT NULL REFERENCES productos (codigo),
    cantidad         INTEGER NOT NULL CHECK (cantidad >= 0),
    minimo           INTEGER NOT NULL CHECK (minimo >= 0),
    PRIMARY KEY (sucursal_codigo, producto_codigo)
);

CREATE TABLE IF NOT EXISTS ingresos_stock (
    numero                   TEXT PRIMARY KEY,
    fecha                    TEXT NOT NULL,
    producto_codigo          TEXT NOT NULL REFERENCES productos (codigo),
    proveedor_codigo         TEXT NOT NULL REFERENCES proveedores (codigo),
    cantidad                 INTEGER NOT NULL CHECK (cantidad > 0),
    costo_unitario_centavos  INTEGER NOT NULL CHECK (costo_unitario_centavos > 0)
);

-- ---------------------------------------------------------------------------
-- Reposición y bultos
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ordenes (
    numero         TEXT PRIMARY KEY,
    fecha          TEXT NOT NULL,
    origen_codigo  TEXT NOT NULL REFERENCES sucursales (codigo),
    cerrada        INTEGER NOT NULL DEFAULT 0 CHECK (cerrada IN (0, 1))
);

CREATE TABLE IF NOT EXISTS detalles_reposicion (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    orden_numero     TEXT NOT NULL REFERENCES ordenes (numero),
    destino_codigo   TEXT NOT NULL REFERENCES sucursales (codigo),
    producto_codigo  TEXT NOT NULL REFERENCES productos (codigo),
    cantidad         INTEGER NOT NULL CHECK (cantidad > 0),
    UNIQUE (orden_numero, destino_codigo, producto_codigo)
);

CREATE TABLE IF NOT EXISTS bultos (
    codigo            TEXT PRIMARY KEY,
    orden_numero      TEXT NOT NULL REFERENCES ordenes (numero),
    destino_codigo    TEXT NOT NULL REFERENCES sucursales (codigo),
    remito_numero     TEXT NOT NULL UNIQUE,
    precinto_numero   TEXT UNIQUE,
    precinto_intacto  INTEGER CHECK (precinto_intacto IN (0, 1)),
    estado            TEXT NOT NULL CHECK (estado IN
        ('PREPARADO', 'PRECINTADO', 'EN_TRANSITO', 'RECIBIDO', 'VERIFICADO', 'RECHAZADO'))
);

CREATE TABLE IF NOT EXISTS detalles_bulto (
    bulto_codigo           TEXT NOT NULL REFERENCES bultos (codigo),
    detalle_reposicion_id  INTEGER NOT NULL REFERENCES detalles_reposicion (id),
    cantidad               INTEGER NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (bulto_codigo, detalle_reposicion_id)
);

CREATE TABLE IF NOT EXISTS historial_estados (
    bulto_codigo  TEXT NOT NULL REFERENCES bultos (codigo),
    secuencia     INTEGER NOT NULL CHECK (secuencia > 0),
    fecha         TEXT NOT NULL,
    anterior      TEXT,
    nuevo         TEXT NOT NULL,
    motivo        TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (bulto_codigo, secuencia)
);

CREATE INDEX IF NOT EXISTS ix_historial_nuevo_fecha ON historial_estados (nuevo, fecha);

-- ---------------------------------------------------------------------------
-- Ventas y devoluciones
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ventas (
    numero                  TEXT PRIMARY KEY,
    fecha                   TEXT NOT NULL,
    local_codigo            TEXT NOT NULL REFERENCES sucursales (codigo),
    medio_codigo            TEXT NOT NULL CHECK (medio_codigo IN ('EFECTIVO', 'TARJETA')),
    tasa_aplicada           TEXT NOT NULL,
    total_cobrado_centavos  INTEGER NOT NULL CHECK (total_cobrado_centavos >= 0),
    comprobante_numero      TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS ix_ventas_fecha ON ventas (fecha);

CREATE TABLE IF NOT EXISTS detalles_venta (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_numero              TEXT NOT NULL REFERENCES ventas (numero),
    producto_codigo           TEXT NOT NULL REFERENCES productos (codigo),
    cantidad                  INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario_centavos  INTEGER NOT NULL CHECK (precio_unitario_centavos > 0),
    costo_unitario_centavos   INTEGER NOT NULL CHECK (costo_unitario_centavos > 0),
    importe_cobrado_centavos  INTEGER NOT NULL CHECK (importe_cobrado_centavos >= 0),
    UNIQUE (venta_numero, producto_codigo)
);

CREATE TABLE IF NOT EXISTS devoluciones (
    numero                        TEXT PRIMARY KEY,
    fecha                         TEXT NOT NULL,
    venta_numero                  TEXT NOT NULL REFERENCES ventas (numero),
    detalle_venta_id              INTEGER NOT NULL REFERENCES detalles_venta (id),
    cantidad                      INTEGER NOT NULL CHECK (cantidad > 0),
    apta_reventa                  INTEGER NOT NULL CHECK (apta_reventa IN (0, 1)),
    motivo                        TEXT NOT NULL CHECK (trim(motivo) <> ''),
    importe_reintegrado_centavos  INTEGER NOT NULL CHECK (importe_reintegrado_centavos >= 0)
);

CREATE INDEX IF NOT EXISTS ix_devoluciones_fecha ON devoluciones (fecha);

-- ---------------------------------------------------------------------------
-- Inmutabilidad (RN-18, RN-21)
-- ---------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS tr_historial_sin_update BEFORE UPDATE ON historial_estados
BEGIN SELECT RAISE(ABORT, 'El historial de estados es inmutable'); END;

CREATE TRIGGER IF NOT EXISTS tr_historial_sin_delete BEFORE DELETE ON historial_estados
BEGIN SELECT RAISE(ABORT, 'El historial de estados es inmutable'); END;

CREATE TRIGGER IF NOT EXISTS tr_detalles_bulto_sin_update BEFORE UPDATE ON detalles_bulto
BEGIN SELECT RAISE(ABORT, 'El contenido de un bulto no se modifica'); END;

CREATE TRIGGER IF NOT EXISTS tr_detalles_bulto_sin_delete BEFORE DELETE ON detalles_bulto
BEGIN SELECT RAISE(ABORT, 'El contenido de un bulto no se modifica'); END;

CREATE TRIGGER IF NOT EXISTS tr_ingresos_sin_update BEFORE UPDATE ON ingresos_stock
BEGIN SELECT RAISE(ABORT, 'Un ingreso registrado no se modifica'); END;

CREATE TRIGGER IF NOT EXISTS tr_ingresos_sin_delete BEFORE DELETE ON ingresos_stock
BEGIN SELECT RAISE(ABORT, 'Un ingreso registrado no se modifica'); END;

CREATE TRIGGER IF NOT EXISTS tr_ventas_sin_update BEFORE UPDATE ON ventas
BEGIN SELECT RAISE(ABORT, 'Una venta confirmada no se modifica'); END;

CREATE TRIGGER IF NOT EXISTS tr_ventas_sin_delete BEFORE DELETE ON ventas
BEGIN SELECT RAISE(ABORT, 'Una venta confirmada no se modifica'); END;

CREATE TRIGGER IF NOT EXISTS tr_detalles_venta_sin_update BEFORE UPDATE ON detalles_venta
BEGIN SELECT RAISE(ABORT, 'Una venta confirmada no se modifica'); END;

CREATE TRIGGER IF NOT EXISTS tr_detalles_venta_sin_delete BEFORE DELETE ON detalles_venta
BEGIN SELECT RAISE(ABORT, 'Una venta confirmada no se modifica'); END;

CREATE TRIGGER IF NOT EXISTS tr_devoluciones_sin_update BEFORE UPDATE ON devoluciones
BEGIN SELECT RAISE(ABORT, 'Una devolución registrada no se modifica'); END;

CREATE TRIGGER IF NOT EXISTS tr_devoluciones_sin_delete BEFORE DELETE ON devoluciones
BEGIN SELECT RAISE(ABORT, 'Una devolución registrada no se modifica'); END;
