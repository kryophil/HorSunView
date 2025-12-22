# -*- coding: utf-8 -*-
"""HorSunView Plugin für QGIS"""
from qgis.core import QgsMessageLog, Qgis
from .gui import HorSunViewPlugin

def classFactory(iface):
    """
    QGIS class factory function.
    :param iface: QGIS interface instance.
    :return: KombiPlugin instance.
    """
    QgsMessageLog.logMessage("Lade HorSunView...", "HorSunView", Qgis.Info)
    return HorSunViewPlugin(iface)
