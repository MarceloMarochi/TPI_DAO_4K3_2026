import { test } from "node:test"
import assert from "node:assert/strict"
import { crearContexto } from "../src/store/contexto"
import { api, ErrorApi, ErrorRed } from "../src/lib/api"
import { coincideVenta } from "../src/lib/operacionVenta"
import type { SolicitudVenta } from "../src/lib/operacionVenta"
import type { Venta } from "../src/lib/tipos"

const error = (estado: number) => new ErrorApi(estado, "ERROR", "Error de prueba", [])
function respuesta(d: SolicitudVenta): Venta {
  return {
    numero: d.numero, fecha: "2026-11-09T10:00:00-03:00", local_codigo: d.local_codigo,
    local_nombre: "Local", medio_codigo: d.medio_codigo, tasa_aplicada: "0.10",
    subtotal: "10.00", ajuste: "-1.00", total_cobrado: d.total_esperado,
    comprobante_numero: `CI-${d.numero}`,
    lineas: d.items.map((i, id) => ({ ...i, id, producto_nombre: "Producto", precio_unitario: "10.00",
      subtotal: "10.00", importe_cobrado: "9.00", cantidad_devuelta: 0,
      importe_devuelto: "0.00", cantidad_restante: i.cantidad })),
  }
}

function preparar(transporte: Parameters<typeof crearContexto>[0]) {
  const store = crearContexto(transporte)
  store.getState().seleccionarLocal("L1")
  store.getState().agregarItem({ producto_codigo: "P1", producto_nombre: "Producto", precio: "10.00" })
  return store
}
function confirmar(store: ReturnType<typeof crearContexto>) {
  return store.getState().confirmarVenta("9.00", store.getState().borrador.version)
}

test("bloquea todas las ediciones y el doble envío mientras espera la respuesta", async () => {
  let resolver!: (v: Venta) => void
  let enviada!: SolicitudVenta
  let envios = 0
  const store = preparar({
    confirmarVenta: (d) => { envios++; enviada = d; return new Promise((r) => { resolver = r }) },
    venta: async () => { throw error(404) },
  })
  const original = store.getState().borrador
  const pendiente = confirmar(store)
  store.getState().cambiarCantidad("P1", 9)
  store.getState().cambiarMedio("TARJETA")
  store.getState().quitarItem("P1")
  store.getState().agregarItem({ producto_codigo: "P2", producto_nombre: "Otro", precio: "1" })
  store.getState().descartarBorrador()
  store.getState().seleccionarLocal("L2")
  await confirmar(store)
  assert.equal(envios, 1)
  assert.equal(store.getState().borrador, original)
  assert.equal(store.getState().localCodigo, "L1")
  assert.ok(Object.isFrozen(enviada.items[0]))
  resolver(respuesta(enviada))
  await pendiente
  assert.equal(store.getState().operacion, null)
  assert.equal(store.getState().confirmada?.numero, original.numero)
  assert.equal(store.getState().borrador.items.length, 0)
})

test("recupera por el mismo número tras respuesta perdida y cambio de vista", async () => {
  let enviada!: SolicitudVenta
  const store = preparar({
    confirmarVenta: async (d) => { enviada = d; throw new ErrorRed() },
    venta: async (n) => { assert.equal(n, enviada.numero); return respuesta(enviada) },
  })
  await confirmar(store)
  assert.equal(store.getState().operacion?.estado, "desconocido")
  // Otro consumidor del mismo store representa el componente montado nuevamente.
  const otraVista = store.getState()
  otraVista.descartarBorrador()
  await otraVista.consultarConfirmacion()
  assert.equal(store.getState().confirmada?.numero, enviada.numero)
})

test("un 404 conserva la solicitud y el reintento no genera otro número", async () => {
  const envios: SolicitudVenta[] = []
  const store = preparar({
    confirmarVenta: async (d) => { envios.push(d); if (envios.length === 1) throw new ErrorRed(); return respuesta(d) },
    venta: async () => { throw error(404) },
  })
  await confirmar(store)
  await store.getState().consultarConfirmacion()
  assert.equal(store.getState().operacion?.estado, "no_encontrada")
  store.getState().descartarBorrador()
  await store.getState().reintentarConfirmacion()
  assert.equal(envios.length, 2)
  assert.equal(envios[0], envios[1])
  assert.equal(store.getState().confirmada?.numero, envios[0].numero)
})

test("un reintento 409 recupera la operación que ya se había confirmado", async () => {
  let enviada!: SolicitudVenta
  const store = preparar({
    confirmarVenta: async (d) => { enviada = d; throw error(409) },
    venta: async () => respuesta(enviada),
  })
  await confirmar(store)
  assert.equal(store.getState().operacion, null)
  assert.equal(store.getState().confirmada?.numero, enviada.numero)
})

test("conflicto sin venta registrada libera el borrador e invalida la cotización", async () => {
  const store = preparar({ confirmarVenta: async () => { throw error(409) }, venta: async () => { throw error(404) } })
  const antes = store.getState().borrador
  await confirmar(store)
  assert.equal(store.getState().operacion, null)
  assert.ok(store.getState().errorVenta instanceof ErrorApi)
  assert.equal(store.getState().borrador.numero, antes.numero)
  assert.ok(store.getState().borrador.version > antes.version)
})

test("rechazo 422 no borra el borrador y permite corregirlo", async () => {
  const store = preparar({ confirmarVenta: async () => { throw error(422) }, venta: async () => { throw error(404) } })
  await confirmar(store)
  assert.equal(store.getState().operacion, null)
  store.getState().cambiarCantidad("P1", 2)
  assert.equal(store.getState().borrador.items[0].cantidad, 2)
})

test("respuesta 500 mantiene resultado desconocido", async () => {
  const store = preparar({ confirmarVenta: async () => { throw error(500) }, venta: async () => { throw error(500) } })
  await confirmar(store)
  await store.getState().consultarConfirmacion()
  assert.equal(store.getState().operacion?.estado, "desconocido")
})

test("no acepta una venta distinta por coincidencia del número", async () => {
  let enviada!: SolicitudVenta
  const store = preparar({
    confirmarVenta: async (d) => { enviada = d; throw new ErrorRed() },
    venta: async () => ({ ...respuesta(enviada), local_codigo: "OTRO" }),
  })
  await confirmar(store)
  await store.getState().consultarConfirmacion()
  assert.equal(store.getState().operacion?.estado, "diferente")
  assert.equal(store.getState().confirmada, null)
  assert.equal(store.getState().borrador.items.length, 1)
  store.getState().resolverNumeroOcupado()
  assert.equal(store.getState().operacion, null)
  assert.notEqual(store.getState().borrador.numero, enviada.numero)
})

test("la comparación usa número, local, medio, total y cantidades", () => {
  const d: SolicitudVenta = { numero: "V", local_codigo: "L", medio_codigo: "EFECTIVO", total_esperado: "9", items: [{ producto_codigo: "P1", cantidad: 1 }] }
  const v = respuesta(d)
  assert.ok(coincideVenta(d, { ...v, total_cobrado: "9.00" }))
  for (const cambio of [{ numero: "OTRA" }, { local_codigo: "OTRO" }, { medio_codigo: "TARJETA" as const }, { total_cobrado: "9.01" }]) {
    assert.equal(coincideVenta(d, { ...v, ...cambio }), false)
  }
  assert.equal(coincideVenta(d, { ...v, lineas: [{ ...v.lineas[0], cantidad: 2 }] }), false)
  assert.equal(coincideVenta(d, { ...v, lineas: [{ ...v.lineas[0], producto_codigo: "P2" }] }), false)
})

test("una cotización de versión vieja no se confirma", async () => {
  let envios = 0
  const store = preparar({ confirmarVenta: async (d) => { envios++; return respuesta(d) }, venta: async () => { throw error(404) } })
  const version = store.getState().borrador.version
  store.getState().cambiarCantidad("P1", 2)
  await store.getState().confirmarVenta("9", version)
  assert.equal(envios, 0)
})

test("JSON truncado en una respuesta exitosa se considera resultado desconocido", async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () => new Response('{"numero":', { status: 201, headers: { "Content-Type": "application/json" } })
  try {
    await assert.rejects(() => api.confirmarVenta({ numero: "V", local_codigo: "L", medio_codigo: "EFECTIVO", total_esperado: "9", items: [] }), ErrorRed)
  } finally {
    globalThis.fetch = original
  }
})
