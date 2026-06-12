"""Diálogo de simulación de ampliación de un préstamo."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
)

from ..core.modelos import Prestamo
from ..core.simulacion import ResultadoSimulacion, simular_ampliacion
from .comunes import fmt_moneda, poblar_cronograma


class DialogoSimulacion(QDialog):
    """Simula una ampliación y, opcionalmente, la guarda como nueva versión.

    Resultados de salida (tras ``exec``):
      - ``aplicar``: True si el usuario decidió guardar la ampliación.
      - ``parametros``: (fecha, monto_extra, cuotas_agregadas) si aplica.
      - ``resultado``: el ResultadoSimulacion mostrado (para exportar).
    """

    def __init__(self, prestamo: Prestamo, parent=None):
        super().__init__(parent)
        self.prestamo = prestamo
        self.aplicar = False
        self.parametros: tuple[date, Decimal, int] | None = None
        self.resultado: ResultadoSimulacion | None = None

        self.setWindowTitle(f"Simular ampliación — {prestamo.cliente.nombre}")
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        layout.addLayout(form)

        # Fecha de ampliación: por defecto, la fecha de la próxima cuota no pagada.
        self.fecha = QDateEdit()
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd/MM/yyyy")
        proxima = self._fecha_sugerida()
        self.fecha.setDate(QDate(proxima.year, proxima.month, proxima.day))

        self.monto_extra = QDoubleSpinBox()
        self.monto_extra.setRange(0.0, 100_000_000)
        self.monto_extra.setDecimals(2)
        self.monto_extra.setGroupSeparatorShown(True)
        self.monto_extra.setValue(0.0)

        self.cuotas_extra = QSpinBox()
        self.cuotas_extra.setRange(0, 600)
        self.cuotas_extra.setValue(0)

        form.addRow("Aplicar desde la fecha:", self.fecha)
        form.addRow("Monto extra (S/):", self.monto_extra)
        form.addRow("Cuotas a agregar (Y):", self.cuotas_extra)

        btn_simular = QPushButton("Recalcular simulación")
        btn_simular.clicked.connect(self._recalcular)
        form.addRow("", btn_simular)

        self.resumen = QLabel("Ajusta los valores y pulsa «Recalcular simulación».")
        self.resumen.setWordWrap(True)
        self.resumen.setStyleSheet("padding:6px; background:#F2F7FF; border-radius:4px;")
        layout.addWidget(self.resumen)

        self.tabla = QTableWidget()
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla)

        fila_btns = QHBoxLayout()
        layout.addLayout(fila_btns)
        self.btn_aplicar = QPushButton("Guardar como nueva versión del préstamo")
        self.btn_aplicar.setEnabled(False)
        self.btn_aplicar.clicked.connect(self._aplicar)
        btn_cerrar = QPushButton("Cerrar (sin guardar)")
        btn_cerrar.clicked.connect(self.reject)
        fila_btns.addWidget(self.btn_aplicar)
        fila_btns.addStretch()
        fila_btns.addWidget(btn_cerrar)

        self._recalcular()

    def _fecha_sugerida(self) -> date:
        for c in self.prestamo.cuotas:
            if not c.pagada:
                return c.fecha
        return self.prestamo.cuotas[-1].fecha if self.prestamo.cuotas else date.today()

    def _recalcular(self) -> None:
        qd = self.fecha.date()
        fecha = date(qd.year(), qd.month(), qd.day())
        monto_extra = Decimal(str(self.monto_extra.value()))
        cuotas_extra = self.cuotas_extra.value()
        try:
            res = simular_ampliacion(self.prestamo, fecha, monto_extra, cuotas_extra)
        except ValueError as e:
            QMessageBox.warning(self, "Simulación inválida", str(e))
            return

        self.resultado = res
        self.parametros = (fecha, monto_extra, cuotas_extra)
        poblar_cronograma(self.tabla, res.cuotas, con_pagos=False)

        total = sum((c.cuota for c in res.cuotas[res.indice_corte:]), Decimal(0))
        self.resumen.setText(
            f"<b>Saldo pendiente a la fecha:</b> {fmt_moneda(res.saldo_base)} &nbsp;|&nbsp; "
            f"<b>+ Monto extra:</b> {fmt_moneda(monto_extra)} &nbsp;=&nbsp; "
            f"<b>Nuevo capital:</b> {fmt_moneda(res.capital_nuevo)}<br>"
            f"<b>Nueva cuota fija:</b> {fmt_moneda(res.cuota_fija)} &nbsp;|&nbsp; "
            f"<b>Cuotas restantes desde la ampliación:</b> "
            f"{len(res.cuotas) - res.indice_corte} &nbsp;|&nbsp; "
            f"<b>Total restante a pagar:</b> {fmt_moneda(total)}"
        )
        self.btn_aplicar.setEnabled(True)

    def _aplicar(self) -> None:
        if self.parametros is None:
            return
        r = QMessageBox.question(
            self,
            "Confirmar",
            "¿Guardar esta simulación como la nueva versión del préstamo?\n"
            "El cronograma actual será reemplazado desde la fecha de ampliación.",
        )
        if r == QMessageBox.StandardButton.Yes:
            self.aplicar = True
            self.accept()
