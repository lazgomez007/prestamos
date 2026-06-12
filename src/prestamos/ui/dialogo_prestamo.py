"""Diálogo para registrar o editar un préstamo."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)

from ..core.modelos import Cliente, Prestamo


class DialogoPrestamo(QDialog):
    """Captura los datos de un préstamo. La tasa se ingresa como % MENSUAL."""

    def __init__(self, parent=None, prestamo: Prestamo | None = None):
        super().__init__(parent)
        self.prestamo = prestamo
        self.setWindowTitle("Editar préstamo" if prestamo else "Nuevo préstamo")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.nombre = QLineEdit()
        self.telefono = QLineEdit()
        self.email = QLineEdit()

        self.monto = QDoubleSpinBox()
        self.monto.setRange(0.01, 100_000_000)
        self.monto.setDecimals(2)
        self.monto.setGroupSeparatorShown(True)
        self.monto.setValue(1000.0)

        self.tasa = QDoubleSpinBox()
        self.tasa.setRange(0.0, 100.0)
        self.tasa.setDecimals(4)
        self.tasa.setSuffix(" %  (mensual)")
        self.tasa.setValue(1.4602)

        self.fecha = QDateEdit()
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd/MM/yyyy")
        self.fecha.setDate(QDate.currentDate())

        self.cuotas = QSpinBox()
        self.cuotas.setRange(1, 600)
        self.cuotas.setValue(12)

        self.notas = QPlainTextEdit()
        self.notas.setPlaceholderText("Notas (opcional)")
        self.notas.setFixedHeight(70)

        form.addRow("Cliente:", self.nombre)
        form.addRow("Teléfono:", self.telefono)
        form.addRow("Email:", self.email)
        form.addRow("Monto (S/):", self.monto)
        form.addRow("Tasa mensual:", self.tasa)
        form.addRow("Fecha de inicio:", self.fecha)
        form.addRow("N° de cuotas:", self.cuotas)
        form.addRow("Notas:", self.notas)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        botones.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

        if prestamo:
            self._cargar(prestamo)

    def _cargar(self, p: Prestamo) -> None:
        self.nombre.setText(p.cliente.nombre)
        self.telefono.setText(p.cliente.telefono)
        self.email.setText(p.cliente.email)
        self.monto.setValue(float(p.monto))
        self.tasa.setValue(float(p.tasa_mensual) * 100)
        self.fecha.setDate(QDate(p.fecha_inicio.year, p.fecha_inicio.month, p.fecha_inicio.day))
        self.cuotas.setValue(p.num_cuotas)
        self.notas.setPlainText(p.notas)

    def _aceptar(self) -> None:
        if not self.nombre.text().strip():
            QMessageBox.warning(self, "Falta dato", "Ingresa el nombre del cliente.")
            return
        try:
            self._resultado = self._construir()
        except (InvalidOperation, ValueError) as e:
            QMessageBox.warning(self, "Dato inválido", str(e))
            return
        self.accept()

    def _construir(self) -> Prestamo:
        qd = self.fecha.date()
        fecha = date(qd.year(), qd.month(), qd.day())
        # La tasa se ingresa en % mensual y se guarda como fracción decimal.
        tasa_fraccion = Decimal(str(self.tasa.value())) / Decimal(100)
        monto = Decimal(str(self.monto.value()))

        if self.prestamo:
            cliente = self.prestamo.cliente
            cliente.nombre = self.nombre.text().strip()
            cliente.telefono = self.telefono.text().strip()
            cliente.email = self.email.text().strip()
            self.prestamo.cliente = cliente
            self.prestamo.monto = monto
            self.prestamo.tasa_mensual = tasa_fraccion
            self.prestamo.fecha_inicio = fecha
            self.prestamo.num_cuotas = self.cuotas.value()
            self.prestamo.notas = self.notas.toPlainText().strip()
            return self.prestamo

        return Prestamo(
            cliente=Cliente(
                nombre=self.nombre.text().strip(),
                telefono=self.telefono.text().strip(),
                email=self.email.text().strip(),
            ),
            monto=monto,
            tasa_mensual=tasa_fraccion,
            fecha_inicio=fecha,
            num_cuotas=self.cuotas.value(),
            notas=self.notas.toPlainText().strip(),
        )

    def resultado(self) -> Prestamo:
        return self._resultado
