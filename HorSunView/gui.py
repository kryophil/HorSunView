# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import (
    QAction,
    QMessageBox,
    QDialog,
    QFormLayout,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QDialogButtonBox
)
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsApplication,
    Qgis
)
import os
from datetime import datetime

from .analysis import HorizonAnalysisTask

class HorSunViewPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None

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
        # Build modal dialog
        dialog = QDialog(self.iface.mainWindow())
        dialog.setModal(True)
        dialog.setWindowTitle(
            QCoreApplication.translate("HorSunView", "HorSunView: Eingaben")
        )
        layout = QFormLayout(dialog)

        # DEM layer selection
        raster_layers = [
            layer for layer in QgsProject.instance().mapLayers().values()
            if isinstance(layer, QgsRasterLayer)
        ]
        combo = QComboBox()
        for layer in raster_layers:
            combo.addItem(layer.name(), layer)
        layout.addRow(
            QCoreApplication.translate("HorSunView", "Höhenmodell:"), combo
        )

        # Coordinates input
        spin_x = QDoubleSpinBox()
        spin_x.setRange(2480000, 2840000)
        spin_x.setDecimals(1)
        layout.addRow(
            QCoreApplication.translate("HorSunView", "Ostwert (LV95):"), spin_x
        )

        spin_y = QDoubleSpinBox()
        spin_y.setRange(1070000, 1296000)
        spin_y.setDecimals(1)
        layout.addRow(
            QCoreApplication.translate("HorSunView", "Nordwert (LV95):"), spin_y
        )

        # Place input
        edit_place = QLineEdit()
        layout.addRow(
            QCoreApplication.translate("HorSunView", "Ort (für Titel):"), edit_place
        )

        # OK / Cancel buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addRow(btn_box)

        # Show dialog
        if dialog.exec_() != QDialog.Accepted:
            return

        # Retrieve inputs after confirmation
        dem_layer = combo.currentData()
        if dem_layer is None:
            QMessageBox.warning(
                None,
                QCoreApplication.translate("HorSunView", "Fehler"),
                QCoreApplication.translate("HorSunView", "Bitte wählen Sie ein Höhenmodell aus.")
            )
            return

        x = spin_x.value()
        y = spin_y.value()

        place = edit_place.text().strip()
        if not place:
            QMessageBox.warning(
                None,
                QCoreApplication.translate("HorSunView", "Fehler"),
                QCoreApplication.translate("HorSunView", "Bitte geben Sie einen Ortsnamen ein.")
            )
            return

        # Ensure QGIS project is saved
        proj_file = QgsProject.instance().fileName()
        if not proj_file:
            QMessageBox.warning(
                None,
                QCoreApplication.translate("HorSunView", "Fehler"),
                QCoreApplication.translate(
                    "HorSunView",
                    "Bitte speichern Sie zuerst Ihr QGIS-Projekt, damit das Ausgabeverzeichnis festgelegt werden kann."
                )
            )
            return
        self.out_dir = os.path.dirname(proj_file)

        # Filename prefix from place
        self.prefix = place.replace(" ", "_")

        # Use current year
        year = datetime.now().year

        # Start background task
        task = HorizonAnalysisTask(dem_layer, x, y, year, place, self.out_dir, self.iface)
        manager = QgsApplication.taskManager()
        manager.addTask(task)

        # Notify user
        self.iface.messageBar().pushMessage(
            "HorSunView",
            QCoreApplication.translate("HorSunView", "Berechnung gestartet..."),
            level=Qgis.Info
        )
        task.progressChanged.connect(
            lambda p: self.iface.messageBar().pushMessage(
                "HorSunView", f"{p}% erledigt", level=Qgis.Info
            )
        )
