import { useCallback, useEffect, useRef, useState } from "react"

/** Carga datos del servidor y expone carga, error y una función para recargar. */
export function useConsulta<T>(cargar: () => Promise<T>, dependencias: unknown[] = []) {
  const [datos, setDatos] = useState<T | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const ultima = useRef(0)

  const recargar = useCallback(async () => {
    const id = ++ultima.current
    setCargando(true)
    setError(null)
    try {
      const resultado = await cargar()
      if (id === ultima.current) setDatos(resultado)
    } catch (e) {
      if (id === ultima.current) setError(e)
    } finally {
      if (id === ultima.current) setCargando(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencias)

  useEffect(() => {
    void recargar()
  }, [recargar])

  return { datos, cargando, error, recargar }
}

/**
 * Ejecuta una operación de escritura. Mientras está pendiente, `pendiente` es true:
 * los botones se deshabilitan para evitar dobles envíos (la garantía real está en el backend).
 */
export function useAccion() {
  const [pendiente, setPendiente] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const ejecutar = useCallback(async <T,>(operacion: () => Promise<T>): Promise<T | undefined> => {
    setPendiente(true)
    setError(null)
    try {
      return await operacion()
    } catch (e) {
      setError(e)
      return undefined
    } finally {
      setPendiente(false)
    }
  }, [])

  return { ejecutar, pendiente, error, limpiarError: () => setError(null) }
}
