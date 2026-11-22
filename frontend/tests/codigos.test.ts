import { test } from "node:test"
import assert from "node:assert/strict"
import { siguienteCodigo, valoresDistintos } from "../src/lib/codigos"

test("sigue la serie existente respetando el ancho", () => {
  assert.equal(siguienteCodigo(["P001", "P010", "P002"], "P", 3), "P011")
  assert.equal(siguienteCodigo(["PRV01", "PRV03"], "PRV", 2), "PRV04")
})

test("ignora códigos fuera de la serie, como el del CD", () => {
  assert.equal(siguienteCodigo(["CD", "L01", "L02", "Especial"], "L", 2), "L03")
})

test("sin registros usa el prefijo y el ancho por defecto", () => {
  assert.equal(siguienteCodigo([], "P", 3), "P001")
})

test("si la serie supera el ancho, crece en lugar de recortar", () => {
  assert.equal(siguienteCodigo(["P999"], "P", 3), "P1000")
})

test("las categorías sugeridas no se repiten por mayúsculas ni espacios", () => {
  assert.deepEqual(valoresDistintos(["Lácteos", "lácteos ", "Almacén", "", "Limpieza"]), ["Almacén", "Lácteos", "Limpieza"])
})
