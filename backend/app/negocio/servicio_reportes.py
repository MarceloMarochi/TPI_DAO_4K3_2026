"""Casos de uso de reportes del alcance simplificado."""
from __future__ import annotations

from decimal import Decimal
from app.negocio.comunes import ahora, redondear
from app.negocio.errores import NoEncontrado
from app.negocio.conversiones import _a_bool
from datetime import date, datetime, time, timedelta
from app.datos.reportes_dao import ReportesDAO
from app.datos.formatos import fecha_a_texto
from app.negocio.comunes import ZONA_HORARIA


class ServicioReportes:
    def __init__(self, conexion):
        self._reportes = ReportesDAO(conexion)

    REPORTES = {
        "ventas": "Ventas e ingresos por local y medio de pago",
        "productos": "Productos vendidos y margen estimado",
        "existencias": "Existencias, mínimos y mercadería en circuito",
        "rechazos": "Rechazos de bultos",
    }

    def consultar_reporte(self, nombre: str, filtros: dict) -> dict:
        """Devuelve {reporte, titulo, generado, filtros, filas, totales, ...} con los indicadores ya calculados.

        Los mismos datos alimentan la respuesta JSON y el PDF.
        """
        calcular = {
            "ventas": self._reporte_ventas,
            "productos": self._reporte_productos,
            "existencias": self._reporte_existencias,
            "rechazos": self._reporte_rechazos,
        }.get(nombre)
        if calcular is None:
            raise NoEncontrado(f"No existe el reporte {nombre}")
        filtros = {clave: valor for clave, valor in filtros.items() if valor not in (None, "")}
        resultado = calcular(filtros)
        return {"reporte": nombre, "titulo": self.REPORTES[nombre], "generado": ahora(),
                "filtros": filtros} | resultado

    def _reporte_ventas(self, filtros) -> dict:
        filas = self._reportes.ventas(
            _periodo(filtros) | {"local": filtros.get("local"), "medio": filtros.get("medio")}
        )
        por_local: dict[str, dict] = {}
        for fila in filas:
            fila["neto"] = fila["cobrado"] - fila["reintegrado"]  # puede ser negativo
            barra = por_local.setdefault(fila["local_codigo"], {
                "local_codigo": fila["local_codigo"], "local_nombre": fila["local_nombre"], "neto": Decimal("0.00")})
            barra["neto"] += fila["neto"]
        return {
            "filas": filas,
            "totales": {
                "cantidad_ventas": sum(f["cantidad_ventas"] for f in filas),
                **{k: _suma(filas, k) for k in ("cobrado", "reintegrado", "neto")},
            },
            "grafico": list(por_local.values()),
        }

    def _reporte_productos(self, filtros) -> dict:
        filas = self._reportes.productos(_periodo(filtros) | {"local": filtros.get("local")})
        for fila in filas:
            fila["unidades_netas"] = fila["vendidas"] - fila["devueltas"]
            fila["importe_neto"] = fila["cobrado"] - fila["reintegrado"]
            fila["costo_neto"] = fila["costo_vendido"] - fila["costo_devuelto"]
            fila["margen"] = fila["importe_neto"] - fila["costo_neto"]
        filas.sort(key=lambda f: (-f["unidades_netas"], -f["margen"], f["producto_codigo"]))
        for posicion, fila in enumerate(filas, start=1):
            fila["posicion"] = posicion
        claves = ("vendidas", "devueltas", "devueltas_aptas", "devueltas_no_aptas", "unidades_netas")
        return {
            "filas": filas,
            "totales": {k: sum(f[k] for f in filas) for k in claves}
                       | {k: _suma(filas, k) for k in ("importe_neto", "costo_neto", "margen")},
        }

    def _reporte_existencias(self, filtros) -> dict:
        filas = self._reportes.existencias(
            {"sucursal": filtros.get("sucursal"), "producto": filtros.get("producto")}
        )
        for fila in filas:
            fila["faltante"] = max(0, fila["minimo"] - fila["disponible"])
            fila["bajo_minimo"] = fila["disponible"] < fila["minimo"]
        if _a_bool(filtros.get("solo_bajo_minimo", False), "solo_bajo_minimo"):
            filas = [f for f in filas if f["bajo_minimo"]]
        return {
            "filas": filas,
            "totales": {
                "filas": len(filas),
                "bajo_minimo": sum(1 for f in filas if f["bajo_minimo"]),
                "faltante": sum(f["faltante"] for f in filas),
                "en_transito": sum(f["en_transito"] for f in filas),
                "recibido_sin_verificar": sum(f["recibido_sin_verificar"] for f in filas),
            },
        }

    def _reporte_rechazos(self, filtros) -> dict:
        consulta = _periodo(filtros) | {"destino": filtros.get("destino")}
        filas = self._reportes.rechazos(consulta)
        for fila in filas:
            fila["finalizados"] = fila["verificados"] + fila["rechazados"]
            fila["porcentaje_rechazo"] = _porcentaje(fila["rechazados"], fila["finalizados"])

        motivos: dict[tuple, dict] = {}
        for rechazo in self._reportes.rechazos_detalle(consulta):
            texto = " ".join((rechazo["motivo"] or "Sin motivo").split()).lower()
            grupo = motivos.setdefault((rechazo["destino_codigo"], texto), {
                "destino_codigo": rechazo["destino_codigo"], "destino_nombre": rechazo["destino_nombre"],
                "motivo": texto[:1].upper() + texto[1:], "bultos": 0, "unidades": 0})
            grupo["bultos"] += 1
            grupo["unidades"] += rechazo["unidades"]

        verificados = sum(f["verificados"] for f in filas)
        rechazados = sum(f["rechazados"] for f in filas)
        return {
            "filas": filas,
            "totales": {
                "verificados": verificados, "rechazados": rechazados, "finalizados": verificados + rechazados,
                # Global con los totales de bultos, no promediando porcentajes de locales.
                "porcentaje_rechazo": _porcentaje(rechazados, verificados + rechazados),
                "unidades_rechazadas": sum(f["unidades_rechazadas"] for f in filas),
            },
            "motivos": sorted(motivos.values(), key=lambda m: (m["destino_codigo"], -m["bultos"], m["motivo"])),
        }


def _a_fecha(valor, campo: str) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise ValueError(f"{campo}: debe ser una fecha AAAA-MM-DD") from None


def _periodo(filtros: dict) -> dict:
    """Desde y hasta inclusivos, en hora de Buenos Aires. Internamente: [desde 00:00, día siguiente a hasta 00:00)."""
    if filtros.get("desde") is None or filtros.get("hasta") is None:
        raise ValueError("desde: el período (desde y hasta) es obligatorio")
    desde = _a_fecha(filtros["desde"], "desde")
    hasta = _a_fecha(filtros["hasta"], "hasta")
    if desde > hasta:
        raise ValueError("hasta: el período está invertido (desde es posterior a hasta)")
    filtros["desde"], filtros["hasta"] = desde, hasta
    inicio = datetime.combine(desde, time.min, tzinfo=ZONA_HORARIA)
    fin = datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=ZONA_HORARIA)
    return {"desde": fecha_a_texto(inicio), "hasta": fecha_a_texto(fin)}


def _suma(filas: list[dict], clave: str) -> Decimal:
    return sum((fila[clave] for fila in filas), Decimal("0.00"))


def _porcentaje(parte: int, total: int) -> Decimal | None:
    """None cuando no hay base: el reporte lo muestra como 'sin datos'."""
    if total == 0:
        return None
    return redondear(Decimal(parte) * 100 / Decimal(total))
