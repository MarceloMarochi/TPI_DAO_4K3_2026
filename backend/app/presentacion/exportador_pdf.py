"""ExportadorPDF: representa en PDF datos ya calculados (reportes y comprobantes).

Usa ReportLab (SimpleDocTemplate, Paragraph, Table) y Matplotlib para el gráfico,
que se guarda en un BytesIO, se reposiciona con seek(0) y se incorpora como imagen.
No ejecuta SQL ni aplica reglas de negocio: sólo da formato.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

import matplotlib

matplotlib.use("Agg")  # sin ventanas: el gráfico se dibuja en memoria, en el servidor
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_RIGHT  # noqa: E402
from reportlab.lib.pagesizes import A4, landscape  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402

from app.negocio.comunes import ZONA_HORARIA  # noqa: E402

# Columnas de cada reporte: (título, clave, tipo). Tipos: texto, entero, importe, porcentaje.
COLUMNAS = {
    "ventas": [
        ("Local", "local_nombre", "texto"), ("Medio", "medio_codigo", "texto"),
        ("Ventas", "cantidad_ventas", "entero"), ("Cobrado", "cobrado", "importe"),
        ("Reintegrado", "reintegrado", "importe"), ("Ingreso neto", "neto", "importe"),
    ],
    "productos": [
        ("#", "posicion", "entero"), ("Producto", "producto_nombre", "texto"),
        ("Vendidas", "vendidas", "entero"), ("Devueltas", "devueltas", "entero"),
        ("Aptas", "devueltas_aptas", "entero"), ("No aptas", "devueltas_no_aptas", "entero"),
        ("Netas", "unidades_netas", "entero"), ("Importe neto", "importe_neto", "importe"),
        ("Costo neto", "costo_neto", "importe"), ("Margen", "margen", "importe"),
    ],
    "existencias": [
        ("Establecimiento", "sucursal_nombre", "texto"), ("Producto", "producto_nombre", "texto"),
        ("Disponible", "disponible", "entero"), ("Mínimo", "minimo", "entero"),
        ("Faltante", "faltante", "entero"), ("Comprometido", "comprometido_salida", "entero"),
        ("Por despachar", "pendiente_despacho", "entero"), ("En tránsito", "en_transito", "entero"),
        ("Sin verificar", "recibido_sin_verificar", "entero"), ("Rechazado", "rechazado", "entero"),
        ("Dev. no apta", "devuelto_no_apto", "entero"),
    ],
    "rechazos": [
        ("Destino", "destino_nombre", "texto"), ("Verificados", "verificados", "entero"),
        ("Rechazados", "rechazados", "entero"), ("Finalizados", "finalizados", "entero"),
        ("% rechazo", "porcentaje_rechazo", "porcentaje"), ("Unidades rechazadas", "unidades_rechazadas", "entero"),
    ],
}

COLUMNAS_MOTIVOS = [
    ("Destino", "destino_nombre", "texto"), ("Motivo", "motivo", "texto"),
    ("Bultos", "bultos", "entero"), ("Unidades", "unidades", "entero"),
]

DEFINICIONES = {
    "ventas": "Ingreso neto = cobrado − reintegrado. Cada flujo se toma por su propia fecha: un reintegro del "
              "período cuenta aunque la venta sea anterior. No es ganancia ni saldo bancario.",
    "productos": "Unidades netas = vendidas − devueltas. Margen estimado = (cobrado − reintegrado) − (costo "
                 "histórico de lo vendido − costo histórico de lo devuelto). No incluye gastos generales.",
    "existencias": "Fotografía actual. Faltante = máximo(0, mínimo − disponible). Lo que está en tránsito, "
                   "recibido sin verificar o rechazado no está habilitado para la venta.",
    "rechazos": "Finalizados = verificados + rechazados en el período (por fecha de la transición final). "
                "% rechazo = rechazados / finalizados × 100. Sin finalizados: sin datos.",
}

NOMBRES_FILTROS = {
    "desde": "Desde", "hasta": "Hasta", "local": "Local", "medio": "Medio de pago",
    "sucursal": "Establecimiento", "producto": "Producto", "destino": "Destino",
    "solo_bajo_minimo": "Sólo bajo mínimo",
}


def formatear_importe(valor: Decimal) -> str:
    """Formato argentino: $ 1.234.567,89 (negativos: -$ 1.234,50)"""
    texto = f"{abs(valor):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{'-' if valor < 0 else ''}$ {texto}"


def formatear_fecha(valor) -> str:
    if isinstance(valor, datetime):
        return valor.astimezone(ZONA_HORARIA).strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def _formatear(valor, tipo: str) -> str:
    if valor is None:
        return "sin datos"
    if tipo == "importe":
        return formatear_importe(valor)
    if tipo == "porcentaje":
        return f"{valor:.2f} %".replace(".", ",")
    return str(valor)


class ExportadorPDF:
    def __init__(self):
        estilos = getSampleStyleSheet()
        self._titulo = estilos["Title"]
        self._subtitulo = estilos["Heading2"]
        self._normal = estilos["Normal"]
        self._nota = ParagraphStyle("nota", parent=estilos["Normal"], fontSize=8, textColor=colors.grey)
        self._derecha = ParagraphStyle("derecha", parent=estilos["Normal"], alignment=TA_RIGHT)

    # ------------------------------------------------------------------
    # Reportes
    # ------------------------------------------------------------------

    def exportar_reporte(self, datos: dict) -> bytes:
        nombre = datos["reporte"]
        elementos = [
            Paragraph(datos["titulo"], self._titulo),
            Paragraph(f"Generado: {formatear_fecha(datos['generado'])}", self._nota),
            Paragraph(self._describir_filtros(datos["filtros"], nombre), self._normal),
            Spacer(1, 0.4 * cm),
        ]
        if not datos["filas"]:
            elementos.append(Paragraph("Sin movimientos para los filtros elegidos.", self._normal))
        else:
            elementos.append(self._tabla(COLUMNAS[nombre], datos["filas"], datos.get("totales")))

        if nombre == "ventas" and datos.get("grafico"):
            elementos += [Spacer(1, 0.6 * cm), Paragraph("Ingreso neto por local", self._subtitulo)]
            grafico = self.crear_grafico(
                [(barra["local_nombre"], barra["neto"]) for barra in datos["grafico"]],
                "Ingreso neto ($)",
            )
            elementos.append(Image(grafico, width=16 * cm, height=8 * cm))

        if nombre == "rechazos" and datos.get("motivos"):
            elementos += [Spacer(1, 0.6 * cm), Paragraph("Rechazos por motivo", self._subtitulo),
                          self._tabla(COLUMNAS_MOTIVOS, datos["motivos"])]

        elementos += [Spacer(1, 0.6 * cm), Paragraph(DEFINICIONES[nombre], self._nota)]
        horizontal = nombre in ("productos", "existencias")
        return self._construir(elementos, horizontal)

    def _describir_filtros(self, filtros: dict, nombre: str) -> str:
        partes = [f"<b>{NOMBRES_FILTROS.get(k, k)}:</b> {formatear_fecha(v) if isinstance(v, date) else v}"
                  for k, v in filtros.items()]
        if nombre == "existencias":
            partes.insert(0, "<b>Corte:</b> situación actual")
        return " · ".join(partes) if partes else "Sin filtros"

    def _tabla(self, columnas, filas: list[dict], totales: dict | None = None) -> Table:
        datos = [[titulo for titulo, _, _ in columnas]]
        for fila in filas:
            datos.append([_formatear(fila.get(clave), tipo) for _, clave, tipo in columnas])
        if totales:
            fila_total = []
            for indice, (_, clave, tipo) in enumerate(columnas):
                if indice == 0:
                    fila_total.append("Total")
                elif clave in totales:
                    fila_total.append(_formatear(totales[clave], tipo))
                else:
                    fila_total.append("")
            datos.append(fila_total)

        tabla = Table(datos, repeatRows=1)
        estilo = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b0b7c3")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f7")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        for indice, (_, _, tipo) in enumerate(columnas):
            if tipo != "texto":
                estilo.append(("ALIGN", (indice, 1), (indice, -1), "RIGHT"))
        if totales:
            estilo += [("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                       ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dde3ea"))]
        tabla.setStyle(TableStyle(estilo))
        return tabla

    def crear_grafico(self, series: list[tuple[str, Decimal]], etiqueta_eje: str) -> BytesIO:
        """Gráfico de barras en memoria. Los netos negativos se dibujan hacia abajo."""
        etiquetas = [nombre for nombre, _ in series]
        valores = [float(valor) for _, valor in series]
        figura, eje = plt.subplots(figsize=(8, 4), dpi=150)
        try:
            barras = eje.bar(etiquetas, valores,
                             color=["#2f6db5" if v >= 0 else "#c0392b" for v in valores])
            eje.axhline(0, color="#555555", linewidth=0.8)
            eje.set_ylabel(etiqueta_eje)
            eje.bar_label(barras, labels=[formatear_importe(Decimal(str(v))) for v in valores], fontsize=7)
            eje.spines[["top", "right"]].set_visible(False)
            figura.tight_layout()
            imagen = BytesIO()
            figura.savefig(imagen, format="png")
        finally:
            plt.close(figura)
        imagen.seek(0)
        return imagen

    # ------------------------------------------------------------------
    # Comprobante interno de venta
    # ------------------------------------------------------------------

    def emitir_comprobante(self, venta: dict) -> bytes:
        elementos = [
            Paragraph("Comprobante interno de venta", self._titulo),
            Paragraph("Documento no válido como factura", self._nota),
            Spacer(1, 0.4 * cm),
            Paragraph(f"<b>Comprobante:</b> {venta['comprobante_numero']} · <b>Venta:</b> {venta['numero']}",
                      self._normal),
            Paragraph(f"<b>Fecha:</b> {formatear_fecha(venta['fecha'])} · "
                      f"<b>Local:</b> {venta['local_nombre']} ({venta['local_codigo']})", self._normal),
            Paragraph(f"<b>Medio de pago:</b> {venta['medio_codigo'].capitalize()}", self._normal),
            Spacer(1, 0.4 * cm),
        ]
        columnas = [
            ("Producto", "producto_nombre", "texto"), ("Cantidad", "cantidad", "entero"),
            ("Precio unitario", "precio_unitario", "importe"), ("Subtotal", "subtotal", "importe"),
        ]
        elementos.append(self._tabla(columnas, venta["lineas"]))
        tipo_ajuste = "Descuento" if venta["ajuste"] < 0 else "Recargo"
        tasa = f"{venta['tasa_aplicada'] * 100:.2f} %".replace(".", ",")
        elementos += [
            Spacer(1, 0.3 * cm),
            Paragraph(f"Subtotal: {formatear_importe(venta['subtotal'])}", self._derecha),
            Paragraph(f"{tipo_ajuste} ({tasa}): {formatear_importe(venta['ajuste'])}", self._derecha),
            Paragraph(f"<b>Total cobrado: {formatear_importe(venta['total_cobrado'])}</b>", self._derecha),
        ]
        return self._construir(elementos)

    # ------------------------------------------------------------------

    @staticmethod
    def _construir(elementos: list, horizontal: bool = False) -> bytes:
        salida = BytesIO()
        documento = SimpleDocTemplate(
            salida, pagesize=landscape(A4) if horizontal else A4,
            leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
            title="Sistema de Ventas e Inventario", author="Grupo G-029",
        )
        documento.build(elementos)
        return salida.getvalue()
