/**
 * Código sugerido para el alta de un catálogo: sigue la serie existente (P010 → P011, PRV03 → PRV04).
 * Es sólo una propuesta editable; el servidor sigue validando que no se repita.
 * Si no hay códigos con la forma prefijo + número, usa el prefijo y el ancho por defecto.
 */
export function siguienteCodigo(existentes: string[], prefijo: string, ancho: number): string {
  const serie = new RegExp(`^${prefijo}(\\d+)$`, "i")
  let mayor = 0
  for (const codigo of existentes) {
    const coincidencia = serie.exec(codigo.trim())
    if (!coincidencia) continue
    mayor = Math.max(mayor, Number(coincidencia[1]))
    ancho = Math.max(ancho, coincidencia[1].length)
  }
  return `${prefijo}${String(mayor + 1).padStart(ancho, "0")}`
}

/** Valores distintos y no vacíos, ordenados, para sugerir en un campo de texto (por ejemplo, categorías). */
export function valoresDistintos(valores: string[]): string[] {
  const vistos = new Map<string, string>()
  for (const valor of valores) {
    const limpio = valor.trim()
    if (limpio && !vistos.has(limpio.toLowerCase())) vistos.set(limpio.toLowerCase(), limpio)
  }
  return [...vistos.values()].sort((a, b) => a.localeCompare(b, "es"))
}
