import { test } from "node:test"
import assert from "node:assert/strict"
import {
  ACCIONES_DEL_AMBITO, AREAS_DEL_AMBITO, accionPendienteEnOtroLugar, accionesEnAmbito, ambitoDe,
} from "../src/lib/contextoOperativo"

test("el CD prepara y despacha; el local recibe y verifica", () => {
  assert.deepEqual(accionesEnAmbito(["precintar"], "cd"), ["precintar"])
  assert.deepEqual(accionesEnAmbito(["precintar"], "local"), [])
  assert.deepEqual(accionesEnAmbito(["recibir"], "local"), ["recibir"])
  assert.deepEqual(accionesEnAmbito(["verificar"], "cd"), [])
})

test("cada acción del ciclo del bulto corresponde a un solo lugar", () => {
  const todas = [...ACCIONES_DEL_AMBITO.cd, ...ACCIONES_DEL_AMBITO.local]
  assert.deepEqual([...todas].sort(), ["despachar", "precintar", "recibir", "verificar"])
})

test("indica qué lugar tiene que hacer la próxima acción", () => {
  assert.deepEqual(accionPendienteEnOtroLugar(["recibir"], "cd"), { accion: "recibir", lugar: "local" })
  assert.deepEqual(accionPendienteEnOtroLugar(["despachar"], "local"), { accion: "despachar", lugar: "cd" })
  assert.equal(accionPendienteEnOtroLugar([], "cd"), null)
})

test("la caja sólo existe en los locales y la logística sólo en el CD", () => {
  assert.equal(ambitoDe(true), "cd")
  assert.ok(AREAS_DEL_AMBITO.local.includes("caja"))
  assert.ok(!AREAS_DEL_AMBITO.cd.includes("caja"))
  assert.ok(AREAS_DEL_AMBITO.cd.includes("logistica"))
  assert.ok(!AREAS_DEL_AMBITO.local.includes("logistica"))
})
