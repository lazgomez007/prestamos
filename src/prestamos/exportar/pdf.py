"""Exportación del estado de cuenta a PDF (reportlab)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..core.calculo import redondear
from ..core.modelos import CuotaRegistro, Prestamo

_AZUL = colors.HexColor("#1F4E78")
_AZUL_CLARO = colors.HexColor("#DDE6F3")
_VERDE = colors.HexColor("#E2EFDA")
_GRIS = colors.HexColor("#F2F2F2")
_TEXTO_SUAVE = colors.HexColor("#595959")

ENCABEZADOS = [
    "N°", "Vencimiento", "N° Días", "Intereses",
    "Amortización", "Cuota", "Saldo Pendiente", "Pagada",
]


def _m(valor: Decimal) -> str:
    return f"S/ {float(redondear(valor)):,.2f}"


def _fecha(f: date | None) -> str:
    return f.strftime("%d/%m/%Y") if f else "—"


def exportar_estado_cuenta(
    prestamo: Prestamo,
    ruta: str | Path,
    cuotas: list[CuotaRegistro] | None = None,
) -> Path:
    """Genera un PDF con el estado de cuenta actual y el cronograma de pagos."""
    cuotas = cuotas if cuotas is not None else prestamo.cuotas
    ruta = Path(ruta)

    estilos = getSampleStyleSheet()
    h_titulo = ParagraphStyle("titulo", parent=estilos["Title"], textColor=_AZUL, fontSize=18)
    h_sub = ParagraphStyle("sub", parent=estilos["Normal"], textColor=_TEXTO_SUAVE, fontSize=10)
    etiqueta = ParagraphStyle("etq", parent=estilos["Normal"], textColor=_TEXTO_SUAVE, fontSize=8)
    valor = ParagraphStyle("val", parent=estilos["Normal"], fontSize=10.5)
    pie = ParagraphStyle("pie", parent=estilos["Normal"], textColor=_TEXTO_SUAVE, fontSize=8, alignment=TA_CENTER)

    doc = SimpleDocTemplate(
        str(ruta), pagesize=landscape(A4),
        leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=12 * mm,
        title=f"Estado de cuenta - {prestamo.cliente.nombre}",
    )
    elementos = []

    # --- Encabezado ---
    elementos.append(Paragraph("Estado de cuenta", h_titulo))
    formula = "B (simple)" if prestamo.formula == "B" else "A (efectiva)"
    elementos.append(Paragraph(
        f"Préstamo {prestamo.id} &nbsp;·&nbsp; {prestamo.cliente.nombre} "
        f"&nbsp;·&nbsp; Estado: <b>{prestamo.estado}</b>", h_sub,
    ))
    elementos.append(Spacer(1, 8))

    # --- Datos del préstamo (dos columnas en una tabla) ---
    def celda(etq, val):
        return [Paragraph(etq, etiqueta), Paragraph(str(val), valor)]

    info = [
        celda("Cliente", prestamo.cliente.nombre) + celda("Monto", _m(prestamo.monto)),
        celda("Teléfono", prestamo.cliente.telefono or "—")
        + celda("Tasa mensual", f"{float(prestamo.tasa_mensual) * 100:.4f}%"),
        celda("Email", prestamo.cliente.email or "—") + celda("Fórmula de interés", formula),
        celda("Fecha de desembolso", _fecha(prestamo.fecha_desembolso))
        + celda("Primer vencimiento", _fecha(prestamo.fecha_primer_vencimiento)),
        celda("N° de cuotas", len(cuotas)) + celda("Emitido", _fecha(datetime.now().date())),
    ]
    t_info = Table(info, colWidths=[35 * mm, 70 * mm, 38 * mm, 70 * mm])
    t_info.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elementos.append(t_info)
    elementos.append(Spacer(1, 10))

    # --- Resumen financiero ---
    total = sum((c.cuota for c in cuotas), Decimal(0))
    interes = sum((c.interes for c in cuotas), Decimal(0))
    amort = sum((c.amortizacion for c in cuotas), Decimal(0))
    pagado = sum((c.cuota for c in cuotas if c.pagada), Decimal(0))
    pagadas = sum(1 for c in cuotas if c.pagada)

    res_etq = ParagraphStyle("retq", parent=etiqueta, alignment=TA_CENTER)
    res_val = ParagraphStyle("rval", parent=estilos["Normal"], fontSize=11, alignment=TA_CENTER, leading=14)
    res_val.fontName = "Helvetica-Bold"

    def rcelda(etq, val):
        return [Paragraph(etq, res_etq), Paragraph(val, res_val)]

    resumen = [
        [Paragraph("Total a pagar", res_etq), Paragraph("Ganancia por intereses", res_etq),
         Paragraph("Capital recuperado", res_etq), Paragraph("Pagado", res_etq),
         Paragraph("Por cobrar", res_etq), Paragraph("Cuotas pagadas", res_etq)],
        [Paragraph(_m(total), res_val), Paragraph(_m(interes), res_val),
         Paragraph(_m(amort), res_val), Paragraph(_m(pagado), res_val),
         Paragraph(_m(total - pagado), res_val), Paragraph(f"{pagadas}/{len(cuotas)}", res_val)],
    ]
    t_res = Table(resumen, colWidths=[(269 * mm) / 6] * 6)
    t_res.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _AZUL_CLARO),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.white),
        ("INNERGRID", (0, 0), (-1, -1), 3, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TEXTCOLOR", (1, 1), (1, 1), colors.HexColor("#1F9D57")),  # ganancia
        ("TEXTCOLOR", (2, 1), (2, 1), _AZUL),                        # capital
    ]))
    elementos.append(t_res)
    elementos.append(Spacer(1, 12))

    # --- Cronograma ---
    datos = [ENCABEZADOS]
    for c in cuotas:
        datos.append([
            str(c.numero), _fecha(c.fecha), str(c.dias), _m(c.interes),
            _m(c.amortizacion), _m(c.cuota), _m(c.saldo), "Sí" if c.pagada else "—",
        ])
    datos.append(["", "", "TOTALES", _m(interes), _m(amort), _m(total), "", ""])

    anchos = [12, 26, 17, 38, 40, 38, 44, 18]
    tabla = Table(datos, colWidths=[w * mm for w in anchos], repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), _AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (3, 0), (6, -1), "RIGHT"),
        ("ALIGN", (0, 0), (2, -1), "CENTER"),
        ("ALIGN", (7, 0), (7, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9D9D9")),
        # Fila de totales
        ("BACKGROUND", (0, -1), (-1, -1), _AZUL_CLARO),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, _AZUL),
    ]
    # Filas alternas y resaltado de cuotas pagadas.
    for i, c in enumerate(cuotas, start=1):
        if c.pagada:
            estilo.append(("BACKGROUND", (0, i), (-1, i), _VERDE))
        elif i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), _GRIS))
    tabla.setStyle(TableStyle(estilo))
    elementos.append(tabla)

    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(
        "Documento generado por Gestor de Préstamos · "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}", pie,
    ))

    doc.build(elementos)
    return ruta
