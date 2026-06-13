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

from ..core.calculo import desglose_carrillo, redondear
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
        celda("Fuente / Entidad", prestamo.fuente) + celda("Estado", prestamo.estado),
        celda("Fecha de desembolso", _fecha(prestamo.fecha_desembolso))
        + celda("Primer vencimiento", _fecha(prestamo.fecha_primer_vencimiento)),
        celda("N° de cuotas", len(cuotas)) + celda("Emitido", _fecha(datetime.now().date())),
    ]
    if prestamo.capital_final and Decimal(prestamo.capital_final) > 0:
        info.append(
            celda("Devolución de capital al final", _m(prestamo.capital_final))
            + celda("Tipo", "Cuota balón")
        )
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

    con_carrillo = bool(
        getattr(prestamo, "tasa_carrillo", 0) and Decimal(prestamo.tasa_carrillo) > 0
    )
    if con_carrillo:
        pares = desglose_carrillo(
            prestamo.monto, prestamo.tasa_carrillo, prestamo.formula, cuotas
        )
        tot_carrillo = sum((ic for ic, _ in pares), Decimal(0))
        tot_mio = sum((im for _, im in pares), Decimal(0))

    res_etq = ParagraphStyle("retq", parent=etiqueta, alignment=TA_CENTER)
    res_val = ParagraphStyle("rval", parent=estilos["Normal"], fontSize=11, alignment=TA_CENTER, leading=14)
    res_val.fontName = "Helvetica-Bold"

    if con_carrillo:
        etqs = ["Total a pagar", "Interés Carrillo", "Mi interés", "Capital recuperado",
                "Pagado", "Por cobrar", "Cuotas pagadas"]
        vals = [_m(total), _m(tot_carrillo), _m(tot_mio), _m(amort),
                _m(pagado), _m(total - pagado), f"{pagadas}/{len(cuotas)}"]
    else:
        etqs = ["Total a pagar", "Ganancia por intereses", "Capital recuperado",
                "Pagado", "Por cobrar", "Cuotas pagadas"]
        vals = [_m(total), _m(interes), _m(amort), _m(pagado),
                _m(total - pagado), f"{pagadas}/{len(cuotas)}"]
    ncol = len(etqs)
    resumen = [
        [Paragraph(e, res_etq) for e in etqs],
        [Paragraph(v, res_val) for v in vals],
    ]
    estilo_res = [
        ("BACKGROUND", (0, 0), (-1, -1), _AZUL_CLARO),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.white),
        ("INNERGRID", (0, 0), (-1, -1), 3, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if con_carrillo:
        estilo_res += [
            ("TEXTCOLOR", (1, 1), (1, 1), colors.HexColor("#6b3fc0")),  # carrillo
            ("TEXTCOLOR", (2, 1), (2, 1), colors.HexColor("#1F9D57")),  # mío
            ("TEXTCOLOR", (3, 1), (3, 1), _AZUL),                        # capital
        ]
    else:
        estilo_res += [
            ("TEXTCOLOR", (1, 1), (1, 1), colors.HexColor("#1F9D57")),
            ("TEXTCOLOR", (2, 1), (2, 1), _AZUL),
        ]
    t_res = Table(resumen, colWidths=[(269 * mm) / ncol] * ncol)
    t_res.setStyle(TableStyle(estilo_res))
    elementos.append(t_res)
    elementos.append(Spacer(1, 12))

    # --- Cronograma ---
    enc = ["N°", "Vencimiento", "N° Días", "Intereses"]
    if con_carrillo:
        enc += ["Int. Carrillo", "Mi interés"]
    enc += ["Amortización", "Cuota", "Saldo Pendiente", "Pagada"]

    # El balón (devolución del capital) se muestra en su propia línea, separado
    # de las cuotas regulares (como en el cronograma oficial).
    con_balon = bool(getattr(prestamo, "capital_final", 0) and Decimal(prestamo.capital_final) > 0)
    regulares = cuotas[:-1] if con_balon else cuotas
    balon = cuotas[-1] if con_balon else None

    datos = [enc]
    for idx, c in enumerate(regulares):
        fila = [str(c.numero), _fecha(c.fecha), str(c.dias), _m(c.interes)]
        if con_carrillo:
            ic, im = pares[idx]
            fila += [_m(ic), _m(im)]
        fila += [_m(c.amortizacion), _m(c.cuota), _m(c.saldo), "Sí" if c.pagada else "—"]
        datos.append(fila)

    # Totales de las cuotas regulares.
    int_reg = sum((c.interes for c in regulares), Decimal(0))
    amort_reg = sum((c.amortizacion for c in regulares), Decimal(0))
    tot_reg = sum((c.cuota for c in regulares), Decimal(0))
    fila_tot = ["", "", "TOTALES", _m(int_reg)]
    if con_carrillo:
        n_reg = len(regulares)
        fila_tot += [_m(sum((ic for ic, _ in pares[:n_reg]), Decimal(0))),
                     _m(sum((im for _, im in pares[:n_reg]), Decimal(0)))]
    fila_tot += [_m(amort_reg), _m(tot_reg), "", ""]
    datos.append(fila_tot)

    if con_balon:
        fila_balon = ["Pago del saldo del capital", "", "", _m(balon.interes)]
        if con_carrillo:
            fila_balon += [_m(Decimal(0)), _m(Decimal(0))]
        fila_balon += [_m(balon.amortizacion), _m(balon.cuota), _m(balon.saldo), "—"]
        datos.append(fila_balon)

    if con_carrillo:
        anchos = [10, 22, 13, 28, 30, 30, 30, 28, 36, 14]
    else:
        anchos = [12, 26, 17, 38, 40, 38, 44, 18]
    n_cols = len(enc)
    saldo_idx = n_cols - 2
    fila_tot_idx = len(regulares) + 1  # índice de la fila de totales
    tabla = Table(datos, colWidths=[w * mm for w in anchos], repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), _AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8 if con_carrillo else 8.5),
        ("ALIGN", (3, 0), (saldo_idx, -1), "RIGHT"),
        ("ALIGN", (0, 0), (2, -1), "CENTER"),
        ("ALIGN", (n_cols - 1, 0), (n_cols - 1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9D9D9")),
        # Fila de totales (cuotas regulares).
        ("BACKGROUND", (0, fila_tot_idx), (-1, fila_tot_idx), _AZUL_CLARO),
        ("FONTNAME", (0, fila_tot_idx), (-1, fila_tot_idx), "Helvetica-Bold"),
        ("LINEABOVE", (0, fila_tot_idx), (-1, fila_tot_idx), 1, _AZUL),
    ]
    if con_carrillo:
        estilo += [
            ("TEXTCOLOR", (4, 1), (4, len(regulares)), colors.HexColor("#6b3fc0")),
            ("TEXTCOLOR", (5, 1), (5, len(regulares)), colors.HexColor("#1F9D57")),
        ]
    if con_balon:
        estilo += [
            ("SPAN", (0, -1), (2, -1)),
            ("ALIGN", (0, -1), (0, -1), "LEFT"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FDF3DA")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]
    for i, c in enumerate(regulares, start=1):
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
