"""Utilidades compartidas por la interfaz (formato y tablas)."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from ..core.modelos import (
    ESTADO_ATRASADO,
    ESTADO_PAGADO,
    CuotaRegistro,
)

COLUMNAS = ["N°", "Fecha", "Días", "Amortización", "Interés", "Cuota", "Saldo Pendiente"]


def fmt_moneda(valor: Decimal | float) -> str:
    return f"S/ {float(valor):,.2f}"


def fmt_pct_mensual(fraccion: Decimal | float) -> str:
    return f"{float(fraccion) * 100:.4f}%"


def _item(texto: str, alinear=Qt.AlignmentFlag.AlignRight) -> QTableWidgetItem:
    it = QTableWidgetItem(texto)
    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
    it.setTextAlignment(alinear | Qt.AlignmentFlag.AlignVCenter)
    return it


def poblar_cronograma(
    tabla: QTableWidget,
    cuotas: list[CuotaRegistro],
    con_pagos: bool = False,
) -> None:
    """Llena una QTableWidget con el cronograma. Si ``con_pagos`` es True,
    agrega una columna de casilla 'Pagada' (editable por el usuario)."""
    columnas = list(COLUMNAS)
    if con_pagos:
        columnas.append("Pagada")
    tabla.clear()
    tabla.setColumnCount(len(columnas))
    tabla.setHorizontalHeaderLabels(columnas)
    tabla.setRowCount(len(cuotas))

    for fila, c in enumerate(cuotas):
        tabla.setItem(fila, 0, _item(str(c.numero), Qt.AlignmentFlag.AlignCenter))
        tabla.setItem(fila, 1, _item(c.fecha.isoformat(), Qt.AlignmentFlag.AlignCenter))
        tabla.setItem(fila, 2, _item(str(c.dias), Qt.AlignmentFlag.AlignCenter))
        tabla.setItem(fila, 3, _item(fmt_moneda(c.amortizacion)))
        tabla.setItem(fila, 4, _item(fmt_moneda(c.interes)))
        tabla.setItem(fila, 5, _item(fmt_moneda(c.cuota)))
        tabla.setItem(fila, 6, _item(fmt_moneda(c.saldo)))

        if con_pagos:
            chk = QTableWidgetItem()
            chk.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            chk.setCheckState(
                Qt.CheckState.Checked if c.pagada else Qt.CheckState.Unchecked
            )
            chk.setData(Qt.ItemDataRole.UserRole, c.id)
            chk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tabla.setItem(fila, 7, chk)

        # Colorear filas pagadas / vencidas.
        if c.pagada:
            color = QColor("#E2EFDA")  # verde claro
        else:
            color = None
        if color:
            for col in range(tabla.columnCount()):
                if tabla.item(fila, col):
                    tabla.item(fila, col).setBackground(color)

    tabla.resizeColumnsToContents()


def color_estado(estado: str) -> QColor:
    if estado == ESTADO_PAGADO:
        return QColor("#70AD47")
    if estado == ESTADO_ATRASADO:
        return QColor("#C00000")
    return QColor("#2E75B6")
