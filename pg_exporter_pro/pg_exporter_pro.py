# -*- coding: utf-8 -*-

"""
/***************************************************************************
 PGExporterPro
                                 A QGIS Plugin
 Export selected PostgreSQL/PostGIS layers to a local offline project.
 Compatible with QGIS 3.22 LTR → 3.40+
 ***************************************************************************/
"""

import os.path

from qgis.PyQt.QtCore import (
    QCoreApplication,
    QLocale,
    QTranslator
)

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from qgis.core import QgsSettings

from .pg_exporter_pro_dialog import PGExporterProDialog


class PGExporterPro:
    """Main plugin class."""

    def __init__(self, iface):
        """
        Constructor.

        Parameters
        ----------
        iface : QgsInterface
            QGIS interface instance.
        """

        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = self.tr("&PG Exporter Pro")

        self.translator = None

        self._load_translation()

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def _load_translation(self):
        """Load translation file if available."""

        locale = QgsSettings().value(
            "locale/userLocale",
            QLocale().name()
        )[:2]

        qm = os.path.join(
            self.plugin_dir,
            "i18n",
            f"{locale}.qm"
        )

        if os.path.exists(qm):
            self.translator = QTranslator()
            self.translator.load(qm)
            QCoreApplication.installTranslator(self.translator)

    def tr(self, text):
        """Translate plugin strings."""
        return QCoreApplication.translate(
            "PGExporterPro",
            text
        )

    # ------------------------------------------------------------------
    # Action Helper
    # ------------------------------------------------------------------

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None
    ):
        """Create a toolbar/menu action."""

        action = QAction(QIcon(icon_path), text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled)

        if status_tip:
            action.setStatusTip(status_tip)

        if whats_this:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action
            )

        self.actions.append(action)

        return action

    # ------------------------------------------------------------------
    # GUI
    # ------------------------------------------------------------------

    def initGui(self):
        """Create toolbar icon and plugin menu."""

        icon = os.path.join(
            self.plugin_dir,
            "icon.png"
        )

        self.add_action(
            icon_path=icon,
            text=self.tr("PG Exporter Pro"),
            callback=self.run,
            parent=self.iface.mainWindow(),
            status_tip=self.tr(
                "Export selected PostgreSQL/PostGIS layers"
            )
        )

    def unload(self):
        """Remove plugin actions."""

        for action in self.actions:
            self.iface.removePluginMenu(
                self.menu,
                action
            )
            self.iface.removeToolBarIcon(action)

        self.actions.clear()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self):
        """
        Open the dialog.

        A fresh dialog is created every time so Plugin Reloader works
        correctly while developing.
        """

        dlg = PGExporterProDialog(
            self.iface.mainWindow()
        )

        dlg.exec()