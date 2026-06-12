"""Ventana principal: lista de préstamos, detalle, pagos y acciones."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..core.modelos import Prestamo
from ..datos.repositorio import Repositorio
from ..exportar.excel import exportar_cronograma
from .comunes import color_estado, fmt_moneda, fmt_pct_mensual, poblar_cronograma
from .dialogo_prestamo import DialogoPrestamo
from .dialogo_simulacion import DialogoSimulacion

COL_LISTA = ["N°", "Cliente", "Monto", "Tasa mensual", "Cuotas", "Estado"]


class VentanaPrincipal(QMainWindow):
    def __init__(self, repo: Repositorio | None = None):
        super().__init__()
        self.repo = repo or Repositorio()
        self.actual: Prestamo | None = None
        self._poblando = False

        self.setWindowTitle("Gestor de Préstamos")
        self.resize(1100, 680)

        self._crear_barra()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        # --- Panel izquierdo: lista de préstamos ---
        self.lista = QTableWidget(0, len(COL_LISTA))
        self.lista.setHorizontalHeaderLabels(COL_LISTA)
        self.lista.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.lista.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.lista.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.lista.itemSelectionChanged.connect(self._cambiar_seleccion)
        splitter.addWidget(self.lista)

        # --- Panel derecho: detalle ---
        splitter.addWidget(self._crear_detalle())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        self.statusBar().showMessage("Listo")
        self.refrescar_lista()

    # ------------------------------------------------------------------ UI
    def _crear_barra(self) -> None:
        barra = QToolBar("Acciones")
        barra.setMovable(False)
        self.addToolBar(barra)

        def accion(texto, slot):
            a = QAction(texto, self)
            a.triggered.connect(slot)
            barra.addAction(a)
            return a

        accion("➕ Nuevo préstamo", self.nuevo_prestamo)
        self.a_editar = accion("✏️ Editar", self.editar_prestamo)
        self.a_simular = accion("📈 Simular ampliación", self.simular_ampliacion)
        self.a_exportar = accion("📊 Exportar a Excel", self.exportar_excel)
        barra.addSeparator()
        self.a_eliminar = accion("🗑️ Eliminar", self.eliminar_prestamo)

    def _crear_detalle(self) -> QWidget:
        cont = QWidget()
        lay = QVBoxLayout(cont)

        self.titulo = QLabel("Selecciona un préstamo")
        self.titulo.setStyleSheet("font-size:16px; font-weight:bold;")
        lay.addWidget(self.titulo)

        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)

        # Pestaña 1: cronograma + pagos
        tab_crono = QWidget()
        l1 = QVBoxLayout(tab_crono)
        self.resumen_pagos = QLabel("")
        self.resumen_pagos.setWordWrap(True)
        l1.addWidget(self.resumen_pagos)
        self.tabla_crono = QTableWidget()
        self.tabla_crono.itemChanged.connect(self._cuota_cambiada)
        l1.addWidget(self.tabla_crono)
        self.tabs.addTab(tab_crono, "Cronograma y pagos")

        # Pestaña 2: datos del cliente / notas
        tab_datos = QWidget()
        l2 = QVBoxLayout(tab_datos)
        self.datos_label = QLabel("")
        self.datos_label.setTextFormat(Qt.TextFormat.RichText)
        l2.addWidget(self.datos_label)
        l2.addWidget(QLabel("Notas:"))
        self.notas_view = QPlainTextEdit()
        self.notas_view.setReadOnly(True)
        l2.addWidget(self.notas_view)
        self.tabs.addTab(tab_datos, "Datos del cliente")

        # Pestaña 3: ampliaciones
        tab_amp = QWidget()
        l3 = QVBoxLayout(tab_amp)
        self.tabla_amp = QTableWidget(0, 4)
        self.tabla_amp.setHorizontalHeaderLabels(
            ["Fecha", "Monto extra", "Cuotas agregadas", "Aplicada"]
        )
        self.tabla_amp.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        l3.addWidget(self.tabla_amp)
        self.tabs.addTab(tab_amp, "Ampliaciones")

        return cont

    # -------------------------------------------------------------- datos
    def refrescar_lista(self) -> None:
        prestamos = self.repo.listar_prestamos()
        self._prestamos = prestamos
        self.lista.setRowCount(len(prestamos))
        for fila, p in enumerate(prestamos):
            valores = [
                f"Préstamo {p.id}",
                p.cliente.nombre,
                fmt_moneda(p.monto),
                fmt_pct_mensual(p.tasa_mensual),
                str(p.num_cuotas),
                p.estado,
            ]
            for col, v in enumerate(valores):
                it = QTableWidgetItem(v)
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 5:
                    it.setForeground(color_estado(p.estado))
                    it.setData(Qt.ItemDataRole.UserRole, p.id)
                self.lista.setItem(fila, col, it)
        self.lista.resizeColumnsToContents()
        self._actualizar_acciones()

    def _cambiar_seleccion(self) -> None:
        fila = self.lista.currentRow()
        if fila < 0 or fila >= len(self._prestamos):
            self.actual = None
        else:
            self.actual = self._prestamos[fila]
        self._mostrar_detalle()
        self._actualizar_acciones()

    def _actualizar_acciones(self) -> None:
        hay = self.actual is not None
        for a in (self.a_editar, self.a_simular, self.a_exportar, self.a_eliminar):
            a.setEnabled(hay)

    def _mostrar_detalle(self) -> None:
        p = self.actual
        if p is None:
            self.titulo.setText("Selecciona un préstamo")
            self._poblando = True
            self.tabla_crono.clear()
            self.tabla_crono.setRowCount(0)
            self._poblando = False
            self.datos_label.setText("")
            self.notas_view.clear()
            self.tabla_amp.setRowCount(0)
            self.resumen_pagos.clear()
            return

        self.titulo.setText(f"Préstamo {p.id} — {p.cliente.nombre}  ·  {p.estado}")

        # Cronograma con pagos
        self._poblando = True
        poblar_cronograma(self.tabla_crono, p.cuotas, con_pagos=True)
        self._poblando = False

        pagadas = sum(1 for c in p.cuotas if c.pagada)
        total = sum((c.cuota for c in p.cuotas), Decimal(0))
        pagado = sum((c.cuota for c in p.cuotas if c.pagada), Decimal(0))
        self.resumen_pagos.setText(
            f"<b>Cuotas pagadas:</b> {pagadas}/{len(p.cuotas)} &nbsp;|&nbsp; "
            f"<b>Total del préstamo:</b> {fmt_moneda(total)} &nbsp;|&nbsp; "
            f"<b>Pagado:</b> {fmt_moneda(pagado)} &nbsp;|&nbsp; "
            f"<b>Por cobrar:</b> {fmt_moneda(total - pagado)}"
        )

        # Datos del cliente
        self.datos_label.setText(
            f"<b>Cliente:</b> {p.cliente.nombre}<br>"
            f"<b>Teléfono:</b> {p.cliente.telefono or '—'}<br>"
            f"<b>Email:</b> {p.cliente.email or '—'}<br><br>"
            f"<b>Monto:</b> {fmt_moneda(p.monto)}<br>"
            f"<b>Tasa mensual:</b> {fmt_pct_mensual(p.tasa_mensual)}<br>"
            f"<b>Fecha de inicio:</b> {p.fecha_inicio.strftime('%d/%m/%Y')}<br>"
            f"<b>N° de cuotas:</b> {p.num_cuotas}<br>"
            f"<b>Estado:</b> {p.estado}"
        )
        self.notas_view.setPlainText(p.notas)

        # Ampliaciones
        self.tabla_amp.setRowCount(len(p.ampliaciones))
        for fila, a in enumerate(p.ampliaciones):
            celdas = [
                a.fecha.strftime("%d/%m/%Y"),
                fmt_moneda(a.monto_extra),
                str(a.cuotas_agregadas),
                a.creada_en.strftime("%d/%m/%Y") if a.creada_en else "—",
            ]
            for col, v in enumerate(celdas):
                it = QTableWidgetItem(v)
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tabla_amp.setItem(fila, col, it)

    # ------------------------------------------------------------ acciones
    def _cuota_cambiada(self, item: QTableWidgetItem) -> None:
        if self._poblando or self.actual is None:
            return
        # Solo la columna "Pagada" (índice 7) tiene casilla.
        if item.column() != 7:
            return
        cuota_id = item.data(Qt.ItemDataRole.UserRole)
        if cuota_id is None:
            return
        pagada = item.checkState() == Qt.CheckState.Checked
        self.repo.marcar_cuota(cuota_id, pagada, date.today() if pagada else None)
        # Recargar para refrescar estado y colores.
        self.actual = self.repo.obtener_prestamo(self.actual.id)
        self._mostrar_detalle()
        self.refrescar_lista()
        self._reseleccionar(self.actual.id)

    def _reseleccionar(self, prestamo_id: int) -> None:
        for fila in range(self.lista.rowCount()):
            it = self.lista.item(fila, 5)
            if it and it.data(Qt.ItemDataRole.UserRole) == prestamo_id:
                self.lista.selectRow(fila)
                return

    def nuevo_prestamo(self) -> None:
        dlg = DialogoPrestamo(self)
        if dlg.exec():
            p = self.repo.crear_prestamo(dlg.resultado())
            self.refrescar_lista()
            self._reseleccionar(p.id)
            self.statusBar().showMessage(f"Préstamo {p.id} creado.")

    def editar_prestamo(self) -> None:
        if self.actual is None:
            return
        original = (
            self.actual.monto, self.actual.tasa_mensual,
            self.actual.fecha_inicio, self.actual.num_cuotas,
        )
        dlg = DialogoPrestamo(self, prestamo=self.repo.obtener_prestamo(self.actual.id))
        if not dlg.exec():
            return
        p = dlg.resultado()
        cambian_terminos = (
            p.monto, p.tasa_mensual, p.fecha_inicio, p.num_cuotas
        ) != original
        if cambian_terminos:
            r = QMessageBox.question(
                self, "Recalcular cronograma",
                "Cambiaste el monto, la tasa, la fecha o el número de cuotas.\n"
                "Esto regenerará el cronograma y se perderán los pagos marcados.\n\n"
                "¿Continuar?",
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self.repo.actualizar_datos_basicos(p, regenerar=cambian_terminos)
        self.refrescar_lista()
        self._reseleccionar(p.id)
        self.statusBar().showMessage("Préstamo actualizado.")

    def eliminar_prestamo(self) -> None:
        if self.actual is None:
            return
        r = QMessageBox.question(
            self, "Eliminar",
            f"¿Eliminar el préstamo {self.actual.id} de {self.actual.cliente.nombre}?\n"
            "Esta acción no se puede deshacer.",
        )
        if r == QMessageBox.StandardButton.Yes:
            self.repo.eliminar_prestamo(self.actual.id)
            self.actual = None
            self.refrescar_lista()
            self._mostrar_detalle()
            self.statusBar().showMessage("Préstamo eliminado.")

    def simular_ampliacion(self) -> None:
        if self.actual is None:
            return
        prestamo = self.repo.obtener_prestamo(self.actual.id)
        dlg = DialogoSimulacion(prestamo, self)
        dlg.exec()
        if dlg.aplicar and dlg.parametros:
            fecha, monto_extra, cuotas_extra = dlg.parametros
            self.repo.aplicar_ampliacion(
                prestamo, fecha, monto_extra, cuotas_extra
            )
            self.refrescar_lista()
            self._reseleccionar(prestamo.id)
            self.statusBar().showMessage("Ampliación aplicada.")

    def exportar_excel(self) -> None:
        if self.actual is None:
            return
        sugerido = f"cronograma_prestamo_{self.actual.id}.xlsx"
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Exportar cronograma", sugerido, "Excel (*.xlsx)"
        )
        if not ruta:
            return
        exportar_cronograma(self.actual, ruta)
        self.statusBar().showMessage(f"Exportado a {ruta}")
        QMessageBox.information(self, "Exportado", f"Cronograma guardado en:\n{ruta}")
