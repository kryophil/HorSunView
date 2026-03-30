# -*- coding: utf-8 -*-
"""
gui.py – HorSunView Plugin-Hauptklasse und Eingabedialog.

Verbesserungen gegenüber Originalversion:
  - Ausgabeverzeichnis frei wählbar (nicht mehr an Projektdatei gebunden)
  - Validierung: Koordinaten werden gegen DEM-Extent geprüft
  - Fortschrittsanzeige: saubere Verbindung ohne Lambda-Spam
  - Koordinaten-Eingabe mit grösserem Standardwert (Schweiz-Mitte)
"""
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import (
    QAction, QMessageBox, QDialog, QFormLayout,
    QComboBox, QDoubleSpinBox, QLineEdit,
    QDialogButtonBox, QFileDialog, QPushButton,
    QHBoxLayout, QWidget, QLabel
)
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProject, QgsRasterLayer, QgsApplication, Qgis
)
import os
from datetime import datetime

from .analysis import HorizonAnalysisTask


class HorSunViewPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self._active_task = None

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icons', 'icon_24.png')
        self.action = QAction(
            QIcon(icon_path),
            QCoreApplication.translate("HorSunView", "HorSunView"),
            self.iface.mainWindow()
        )
        self.action.triggered.connect(self.show_input_dialog)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(
            QCoreApplication.translate("HorSunView", "&HorSunView"),
            self.action
        )

    def unload(self):
        self.iface.removePluginMenu(
            QCoreApplication.translate("HorSunView", "&HorSunView"),
            self.action
        )
        self.iface.removeToolBarIcon(self.action)

    def show_input_dialog(self):
        # ---- Rasterlayer sammeln ----
        raster_layers = [
            layer for layer in QgsProject.instance().mapLayers().values()
            if isinstance(layer, QgsRasterLayer)
        ]
        if not raster_layers:
            QMessageBox.warning(
                self.iface.mainWindow(),
                QCoreApplication.translate("HorSunView", "Kein Höhenmodell"),
                QCoreApplication.translate(
                    "HorSunView",
                    "Bitte laden Sie zuerst ein DEM-Rasterlayer in Ihr QGIS-Projekt."
                )
            )
            return

        # ---- Dialog aufbauen ----
        dialog = QDialog(self.iface.mainWindow())
        dialog.setModal(True)
        dialog.setWindowTitle(
            QCoreApplication.translate("HorSunView", "HorSunView – Eingaben")
        )
        dialog.setMinimumWidth(420)
        layout = QFormLayout(dialog)
        layout.setRowWrapPolicy(QFormLayout.WrapLongRows)

        # DEM-Auswahl
        combo = QComboBox()
        for layer in raster_layers:
            combo.addItem(layer.name(), layer)
        layout.addRow(
            QCoreApplication.translate("HorSunView", "Höhenmodell (DEM):"), combo
        )

        # Koordinaten (LV95)
        spin_e = QDoubleSpinBox()
        spin_e.setRange(2480000, 2840000)
        spin_e.setDecimals(1)
        spin_e.setSingleStep(100)
        spin_e.setValue(2600000)  # Schweiz-Mitte als Startwert
        spin_e.setSuffix(" m")
        layout.addRow(
            QCoreApplication.translate("HorSunView", "Ostwert E (LV95):"), spin_e
        )

        spin_n = QDoubleSpinBox()
        spin_n.setRange(1070000, 1296000)
        spin_n.setDecimals(1)
        spin_n.setSingleStep(100)
        spin_n.setValue(1200000)
        spin_n.setSuffix(" m")
        layout.addRow(
            QCoreApplication.translate("HorSunView", "Nordwert N (LV95):"), spin_n
        )

        # Ortsname
        edit_place = QLineEdit()
        edit_place.setPlaceholderText("z. B. Grindelwald")
        layout.addRow(
            QCoreApplication.translate("HorSunView", "Ortsname (Titel/Prefix):"), edit_place
        )

        # Azimut-Auflösung
        spin_az = QDoubleSpinBox()
        spin_az.setRange(0.1, 2.0)
        spin_az.setSingleStep(0.1)
        spin_az.setDecimals(1)
        spin_az.setValue(0.5)
        spin_az.setSuffix(" °")
        spin_az.setToolTip(
            QCoreApplication.translate(
                "HorSunView",
                "Winkelauflösung des Horizontprofils.\n"
                "0.5° = Standardwert (guter Kompromiss Genauigkeit/Geschwindigkeit)\n"
                "0.25° = höhere Auflösung (2× langsamer)\n"
                "1.0° = schnell, ausreichend für grobe SVF-Schätzung"
            )
        )
        layout.addRow(
            QCoreApplication.translate("HorSunView", "Azimut-Auflösung:"), spin_az
        )

        # Ausgabeverzeichnis
        out_dir_edit = QLineEdit()
        # Vorschlag: Projektordner falls vorhanden, sonst Home
        proj_file = QgsProject.instance().fileName()
        default_out = os.path.dirname(proj_file) if proj_file else os.path.expanduser("~")
        out_dir_edit.setText(default_out)

        btn_browse = QPushButton("…")
        btn_browse.setFixedWidth(32)
        btn_browse.setToolTip(
            QCoreApplication.translate("HorSunView", "Ausgabeverzeichnis wählen")
        )

        def browse_dir():
            d = QFileDialog.getExistingDirectory(
                dialog,
                QCoreApplication.translate("HorSunView", "Ausgabeverzeichnis wählen"),
                out_dir_edit.text()
            )
            if d:
                out_dir_edit.setText(d)

        btn_browse.clicked.connect(browse_dir)

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(out_dir_edit)
        row_layout.addWidget(btn_browse)
        layout.addRow(
            QCoreApplication.translate("HorSunView", "Ausgabeverzeichnis:"), row_widget
        )

        # Hinweistext
        hint = QLabel(
            QCoreApplication.translate(
                "HorSunView",
                "<small>Koordinaten im Schweizer Koordinatensystem LV95 (EPSG:2056).<br>"
                "Beobachterhöhe: Geländehöhe + 2 m. Sichtweite: 10 km.<br>"
                "Erdkrümmungskorrektur ist aktiv.</small>"
            )
        )
        hint.setWordWrap(True)
        layout.addRow(hint)

        # OK / Cancel
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Ok).setText(
            QCoreApplication.translate("HorSunView", "Berechnen")
        )
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addRow(btn_box)

        if dialog.exec_() != QDialog.Accepted:
            return

        # ---- Eingaben auslesen & validieren ----
        dem_layer = combo.currentData()
        x = spin_e.value()
        y = spin_n.value()
        place = edit_place.text().strip()
        out_dir = out_dir_edit.text().strip()
        az_step = spin_az.value()

        errors = []
        if dem_layer is None:
            errors.append(QCoreApplication.translate("HorSunView", "Kein Höhenmodell ausgewählt."))
        if not place:
            errors.append(QCoreApplication.translate("HorSunView", "Bitte einen Ortsnamen eingeben."))
        if not out_dir or not os.path.isdir(out_dir):
            errors.append(QCoreApplication.translate(
                "HorSunView", "Ausgabeverzeichnis existiert nicht oder ist ungültig."
            ))

        # Koordinatenvalidierung gegen DEM-Extent
        if dem_layer is not None:
            ext = dem_layer.extent()
            if not (ext.xMinimum() <= x <= ext.xMaximum() and
                    ext.yMinimum() <= y <= ext.yMaximum()):
                errors.append(
                    QCoreApplication.translate(
                        "HorSunView",
                        f"Koordinaten ({x:.0f}, {y:.0f}) liegen ausserhalb des gewählten DEM:\n"
                        f"  E: {ext.xMinimum():.0f} – {ext.xMaximum():.0f}\n"
                        f"  N: {ext.yMinimum():.0f} – {ext.yMaximum():.0f}"
                    )
                )

        if errors:
            QMessageBox.warning(
                self.iface.mainWindow(),
                QCoreApplication.translate("HorSunView", "Eingabefehler"),
                "\n\n".join(errors)
            )
            return

        # ---- Task starten ----
        year = datetime.now().year
        task = HorizonAnalysisTask(dem_layer, x, y, year, place, out_dir, self.iface,
                                   az_step=az_step)
        self._active_task = task  # Referenz halten, sonst kann GC zuschlagen

        QgsApplication.taskManager().addTask(task)

        self.iface.messageBar().pushMessage(
            "HorSunView",
            QCoreApplication.translate(
                "HorSunView",
                f"Berechnung gestartet für {place} ({x:.0f}, {y:.0f}) …"
            ),
            level=Qgis.Info,
            duration=4
        )
