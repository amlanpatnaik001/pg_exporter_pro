# -*- coding: utf-8 -*-

"""
/***************************************************************************
 PGExporterProDialog
                                 A QGIS Plugin
 Export selected PostgreSQL/PostGIS layers to a local offline project.

 PG Exporter Pro
 Qt5 / Qt6 compatible
 QGIS 3.x / QGIS 4.x compatible
 ***************************************************************************/
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QCheckBox,
    QProgressBar,
    QMessageBox,
    QGroupBox,
    QFormLayout
)

from qgis.PyQt.QtGui import QFont

from qgis.core import (
    QgsProject,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer
)

from .exporter import ExportEngine


# ============================================================================
# QT5 / QT6 COMPATIBILITY
# ============================================================================

def qt_enum(enum_class_name, member_name, legacy_name):
    """
    Resolve Qt enum values for both Qt5 and Qt6.
    """

    # ----------------------------------------------------------------------
    # Qt6
    # ----------------------------------------------------------------------

    enum_class = getattr(
        Qt,
        enum_class_name,
        None
    )

    if enum_class is not None:

        member = getattr(
            enum_class,
            member_name,
            None
        )

        if member is not None:
            return member

    # ----------------------------------------------------------------------
    # Qt5
    # ----------------------------------------------------------------------

    member = getattr(
        Qt,
        legacy_name,
        None
    )

    if member is not None:
        return member

    raise AttributeError(
        "Qt enum not available: "
        f"{enum_class_name}.{member_name}"
    )


# ============================================================================
# ITEM FLAGS
# ============================================================================

ITEM_IS_USER_CHECKABLE = qt_enum(
    "ItemFlag",
    "ItemIsUserCheckable",
    "ItemIsUserCheckable"
)

ITEM_IS_AUTOTRISTATE = qt_enum(
    "ItemFlag",
    "ItemIsAutoTristate",
    "ItemIsAutoTristate"
)


# ============================================================================
# ITEM DATA ROLE
# ============================================================================

USER_ROLE = qt_enum(
    "ItemDataRole",
    "UserRole",
    "UserRole"
)


# ============================================================================
# CHECK STATES
# ============================================================================

CHECKED = qt_enum(
    "CheckState",
    "Checked",
    "Checked"
)

UNCHECKED = qt_enum(
    "CheckState",
    "Unchecked",
    "Unchecked"
)

PARTIALLY_CHECKED = qt_enum(
    "CheckState",
    "PartiallyChecked",
    "PartiallyChecked"
)


# ============================================================================
# MESSAGE BOX BUTTONS
# ============================================================================

try:

    # Qt6 / PyQt6
    MSG_YES = QMessageBox.StandardButton.Yes
    MSG_NO = QMessageBox.StandardButton.No

except AttributeError:

    # Qt5 / PyQt5
    MSG_YES = QMessageBox.Yes
    MSG_NO = QMessageBox.No


# ============================================================================
# MAIN DIALOG
# ============================================================================

class PGExporterProDialog(QDialog):
    """Main PG Exporter Pro dialog."""

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setWindowTitle(
            "PG Exporter Pro"
        )

        self.resize(
            920,
            760
        )

        self.setMinimumSize(
            820,
            680
        )

        # ------------------------------------------------------------------
        # Internal state
        # ------------------------------------------------------------------

        self._building_tree = False
        self._updating_checks = False
        self._tree_initialized = False

        # ------------------------------------------------------------------
        # Build UI
        # ------------------------------------------------------------------

        self.build_ui()

        # ------------------------------------------------------------------
        # Populate
        # ------------------------------------------------------------------

        self.populate_tree(
            preserve_selection=False
        )

    # ======================================================================
    # BUILD UI
    # ======================================================================

    def build_ui(self):

        main_layout = QVBoxLayout(
            self
        )

        main_layout.setContentsMargins(
            14,
            14,
            14,
            14
        )

        main_layout.setSpacing(
            10
        )

        # ------------------------------------------------------------------
        # HEADER
        # ------------------------------------------------------------------

        title = QLabel(
            "PG Exporter Pro"
        )

        title_font = QFont()

        title_font.setPointSize(
            18
        )

        title_font.setBold(
            True
        )

        title.setFont(
            title_font
        )

        subtitle = QLabel(
            "PostgreSQL / PostGIS → Local QGIS Project"
        )

        self.lblDatabase = QLabel(
            "Database: Detecting..."
        )

        self.lblSelected = QLabel(
            "Selected layers: 0"
        )

        main_layout.addWidget(
            title
        )

        main_layout.addWidget(
            subtitle
        )

        main_layout.addWidget(
            self.lblDatabase
        )

        main_layout.addWidget(
            self.lblSelected
        )

        # ------------------------------------------------------------------
        # LAYER GROUP
        # ------------------------------------------------------------------

        layer_group = QGroupBox(
            "PostgreSQL / PostGIS Layers"
        )

        layer_layout = QVBoxLayout(
            layer_group
        )

        self.layerTree = QTreeWidget()

        self.layerTree.setHeaderHidden(
            True
        )

        self.layerTree.setAlternatingRowColors(
            True
        )

        self.layerTree.itemChanged.connect(
            self._on_item_changed
        )

        layer_layout.addWidget(
            self.layerTree
        )

        # ------------------------------------------------------------------
        # LAYER BUTTONS
        # ------------------------------------------------------------------

        layer_buttons = QHBoxLayout()

        self.selectAllBtn = QPushButton(
            "Select All"
        )

        self.clearAllBtn = QPushButton(
            "Clear All"
        )

        self.refreshBtn = QPushButton(
            "Refresh"
        )

        self.selectAllBtn.clicked.connect(
            self.select_all_layers
        )

        self.clearAllBtn.clicked.connect(
            self.clear_all_layers
        )

        self.refreshBtn.clicked.connect(
            self.refresh_tree
        )

        layer_buttons.addWidget(
            self.selectAllBtn
        )

        layer_buttons.addWidget(
            self.clearAllBtn
        )

        layer_buttons.addWidget(
            self.refreshBtn
        )

        layer_buttons.addStretch()

        layer_layout.addLayout(
            layer_buttons
        )

        main_layout.addWidget(
            layer_group,
            1
        )

        # ------------------------------------------------------------------
        # OUTPUT
        # ------------------------------------------------------------------

        output_group = QGroupBox(
            "Output"
        )

        output_layout = QFormLayout(
            output_group
        )

        output_row = QHBoxLayout()

        self.outputEdit = QLineEdit()

        self.outputEdit.setPlaceholderText(
            "Choose an output folder..."
        )

        self.browseBtn = QPushButton(
            "Browse..."
        )

        self.browseBtn.clicked.connect(
            self.browse
        )

        output_row.addWidget(
            self.outputEdit,
            1
        )

        output_row.addWidget(
            self.browseBtn
        )

        output_layout.addRow(
            "Folder:",
            output_row
        )

        main_layout.addWidget(
            output_group
        )

        # ------------------------------------------------------------------
        # OPTIONS
        # ------------------------------------------------------------------

        options_group = QGroupBox(
            "Export Options"
        )

        options_layout = QVBoxLayout(
            options_group
        )

        self.chkHierarchy = QCheckBox(
            "Preserve layer hierarchy"
        )

        self.chkHierarchy.setChecked(
            True
        )

        self.chkStyles = QCheckBox(
            "Preserve layer styles (.qml)"
        )

        self.chkStyles.setChecked(
            True
        )

        self.chkLabels = QCheckBox(
            "Preserve labels"
        )

        self.chkLabels.setChecked(
            True
        )

        self.chkVisible = QCheckBox(
            "Visible layers only"
        )

        self.chkVisible.setChecked(
            True
        )

        self.chkVisible.toggled.connect(
            self._visible_filter_changed
        )

        options_layout.addWidget(
            self.chkHierarchy
        )

        options_layout.addWidget(
            self.chkStyles
        )

        options_layout.addWidget(
            self.chkLabels
        )

        options_layout.addWidget(
            self.chkVisible
        )

        main_layout.addWidget(
            options_group
        )

        # ------------------------------------------------------------------
        # STATUS
        # ------------------------------------------------------------------

        self.statusLabel = QLabel(
            "Ready"
        )

        self.progress = QProgressBar()

        self.progress.setRange(
            0,
            100
        )

        self.progress.setValue(
            0
        )

        main_layout.addWidget(
            self.statusLabel
        )

        main_layout.addWidget(
            self.progress
        )

        # ------------------------------------------------------------------
        # BOTTOM BUTTONS
        # ------------------------------------------------------------------

        bottom_layout = QHBoxLayout()

        bottom_layout.addStretch()

        self.closeBtn = QPushButton(
            "Close"
        )

        self.exportBtn = QPushButton(
            "Export Selected Layers"
        )

        self.closeBtn.clicked.connect(
            self.reject
        )

        self.exportBtn.clicked.connect(
            self.export_clicked
        )

        bottom_layout.addWidget(
            self.closeBtn
        )

        bottom_layout.addWidget(
            self.exportBtn
        )

        main_layout.addLayout(
            bottom_layout
        )

    # ======================================================================
    # BROWSE
    # ======================================================================

    def browse(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder"
        )

        if folder:

            self.outputEdit.setText(
                folder
            )

    # ======================================================================
    # REFRESH TREE
    # ======================================================================

    def refresh_tree(self):

        self.populate_tree(
            preserve_selection=True
        )

    # ======================================================================
    # VISIBILITY
    # ======================================================================

    def _node_visible(
        self,
        node
    ):

        try:

            method = getattr(
                node,
                "isVisible",
                None
            )

            if callable(method):

                return bool(
                    method()
                )

        except Exception:
            pass

        try:

            method = getattr(
                node,
                "itemVisibilityChecked",
                None
            )

            if callable(method):

                return bool(
                    method()
                )

        except Exception:
            pass

        return True

    # ======================================================================
    # PROVIDER URI
    # ======================================================================

    def _provider_uri(
        self,
        layer
    ):

        try:

            return (
                layer
                .dataProvider()
                .uri()
                .connectionInfo()
            )

        except Exception:
            pass

        try:

            return layer.source()

        except Exception:

            return ""

    # ======================================================================
    # DATABASE NAME
    # ======================================================================

    def _extract_database_name(
        self,
        connection
    ):

        if not connection:

            return "Unknown"

        for part in connection.split():

            if part.startswith(
                "dbname="
            ):

                value = part.split(
                    "=",
                    1
                )[1]

                return value.strip(
                    "'\""
                )

        return "PostgreSQL / PostGIS"

    # ======================================================================
    # POPULATE TREE
    # ======================================================================

    def populate_tree(
        self,
        preserve_selection=True
    ):

        # --------------------------------------------------------------
        # Save selected IDs before rebuilding
        # --------------------------------------------------------------

        selected_ids = set()

        if (
            preserve_selection
            and self._tree_initialized
        ):

            try:

                selected_ids = set(
                    layer.id()
                    for layer
                    in self.selected_layers()
                )

            except Exception:

                selected_ids = set()

        # --------------------------------------------------------------
        # Build
        # --------------------------------------------------------------

        self._building_tree = True

        try:

            self.layerTree.clear()

            root = (
                QgsProject.instance()
                .layerTreeRoot()
            )

            self._add_node(
                root,
                self.layerTree.invisibleRootItem(),
                selected_ids
            )

            self.layerTree.expandAll()

            self._update_database_label()

            self._update_selected_count()

            self._tree_initialized = True

        finally:

            self._building_tree = False

    # ======================================================================
    # DATABASE LABEL
    # ======================================================================

    def _update_database_label(self):

        database_names = []

        for layer in (
            QgsProject.instance()
            .mapLayers()
            .values()
        ):

            if layer.providerType() != "postgres":

                continue

            database = (
                self._extract_database_name(
                    self._provider_uri(
                        layer
                    )
                )
            )

            if database not in database_names:

                database_names.append(
                    database
                )

        if database_names:

            self.lblDatabase.setText(
                "Database: "
                + ", ".join(
                    database_names
                )
            )

        else:

            self.lblDatabase.setText(
                "Database: No PostgreSQL/PostGIS "
                "layer detected"
            )

    # ======================================================================
    # ADD TREE NODE
    # ======================================================================

    def _add_node(
        self,
        node,
        parent_item,
        selected_ids
    ):

        for child in node.children():

            # ==============================================================
            # GROUP
            # ==============================================================

            if isinstance(
                child,
                QgsLayerTreeGroup
            ):

                # ----------------------------------------------------------
                # Only display groups containing PostgreSQL layers
                # ----------------------------------------------------------

                if not self._group_contains_postgres(
                    child
                ):

                    continue

                item = QTreeWidgetItem(
                    parent_item
                )

                item.setText(
                    0,
                    child.name()
                )

                item.setFlags(
                    item.flags()
                    | ITEM_IS_USER_CHECKABLE
                    | ITEM_IS_AUTOTRISTATE
                )

                item.setCheckState(
                    0,
                    CHECKED
                )

                # ----------------------------------------------------------
                # Preserve expanded state
                # ----------------------------------------------------------

                try:

                    item.setExpanded(
                        child.isExpanded()
                    )

                except Exception:

                    pass

                self._add_node(
                    child,
                    item,
                    selected_ids
                )

                # ----------------------------------------------------------
                # Recalculate group state
                # ----------------------------------------------------------

                self._update_parent_check_state(
                    item
                )

            # ==============================================================
            # LAYER
            # ==============================================================

            elif isinstance(
                child,
                QgsLayerTreeLayer
            ):

                layer = child.layer()

                if layer is None:

                    continue

                # ----------------------------------------------------------
                # PostgreSQL / PostGIS only
                # ----------------------------------------------------------

                if layer.providerType() != "postgres":

                    continue

                # ----------------------------------------------------------
                # Visible-only mode
                # ----------------------------------------------------------

                if (
                    self.chkVisible.isChecked()
                    and not self._node_visible(
                        child
                    )
                ):

                    continue

                item = QTreeWidgetItem(
                    parent_item
                )

                item.setText(
                    0,
                    layer.name()
                )

                item.setFlags(
                    item.flags()
                    | ITEM_IS_USER_CHECKABLE
                )

                # ----------------------------------------------------------
                # Initial selection
                # ----------------------------------------------------------

                if (
                    self._tree_initialized
                    and selected_ids
                ):

                    if layer.id() in selected_ids:

                        item.setCheckState(
                            0,
                            CHECKED
                        )

                    else:

                        item.setCheckState(
                            0,
                            UNCHECKED
                        )

                else:

                    item.setCheckState(
                        0,
                        CHECKED
                    )

                # ----------------------------------------------------------
                # Store layer ID
                # ----------------------------------------------------------

                item.setData(
                    0,
                    USER_ROLE,
                    layer.id()
                )

    # ======================================================================
    # GROUP CONTAINS POSTGRES
    # ======================================================================

    def _group_contains_postgres(
        self,
        group
    ):

        for child in group.children():

            # --------------------------------------------------------------
            # Layer
            # --------------------------------------------------------------

            if isinstance(
                child,
                QgsLayerTreeLayer
            ):

                layer = child.layer()

                if layer is None:

                    continue

                if layer.providerType() != "postgres":

                    continue

                if (
                    self.chkVisible.isChecked()
                    and not self._node_visible(
                        child
                    )
                ):

                    continue

                return True

            # --------------------------------------------------------------
            # Nested group
            # --------------------------------------------------------------

            elif isinstance(
                child,
                QgsLayerTreeGroup
            ):

                if self._group_contains_postgres(
                    child
                ):

                    return True

        return False

    # ======================================================================
    # ITEM CHANGED
    # ======================================================================

    def _on_item_changed(
        self,
        item,
        column
    ):

        if self._building_tree:

            return

        if self._updating_checks:

            return

        if column != 0:

            return

        # --------------------------------------------------------------
        # If this is a group, propagate explicit
        # Checked / Unchecked state to children.
        # --------------------------------------------------------------

        if item.childCount() > 0:

            state = item.checkState(
                0
            )

            if state == CHECKED:

                self._updating_checks = True

                try:

                    self._set_children_state(
                        item,
                        CHECKED
                    )

                finally:

                    self._updating_checks = False

            elif state == UNCHECKED:

                self._updating_checks = True

                try:

                    self._set_children_state(
                        item,
                        UNCHECKED
                    )

                finally:

                    self._updating_checks = False

        self._update_selected_count()

    # ======================================================================
    # SET CHILDREN STATE
    # ======================================================================

    def _set_children_state(
        self,
        item,
        state
    ):

        for i in range(
            item.childCount()
        ):

            child = item.child(
                i
            )

            child.setCheckState(
                0,
                state
            )

            if child.childCount() > 0:

                self._set_children_state(
                    child,
                    state
                )

    # ======================================================================
    # UPDATE PARENT STATE
    # ======================================================================

    def _update_parent_check_state(
        self,
        item
    ):

        if item.childCount() == 0:

            return

        checked = 0
        unchecked = 0
        partial = 0

        for i in range(
            item.childCount()
        ):

            state = item.child(i).checkState(
                0
            )

            if state == CHECKED:

                checked += 1

            elif state == UNCHECKED:

                unchecked += 1

            else:

                partial += 1

        # --------------------------------------------------------------
        # All children checked
        # --------------------------------------------------------------

        if (
            checked > 0
            and unchecked == 0
            and partial == 0
        ):

            item.setCheckState(
                0,
                CHECKED
            )

        # --------------------------------------------------------------
        # All children unchecked
        # --------------------------------------------------------------

        elif (
            unchecked > 0
            and checked == 0
            and partial == 0
        ):

            item.setCheckState(
                0,
                UNCHECKED
            )

        # --------------------------------------------------------------
        # Mixed
        # --------------------------------------------------------------

        else:

            item.setCheckState(
                0,
                PARTIALLY_CHECKED
            )

    # ======================================================================
    # SELECT ALL
    # ======================================================================

    def select_all_layers(self):

        root = (
            self.layerTree
            .invisibleRootItem()
        )

        self._updating_checks = True

        try:

            self._set_children_state(
                root,
                CHECKED
            )

        finally:

            self._updating_checks = False

        self._update_selected_count()

    # ======================================================================
    # CLEAR ALL
    # ======================================================================

    def clear_all_layers(self):

        root = (
            self.layerTree
            .invisibleRootItem()
        )

        self._updating_checks = True

        try:

            self._set_children_state(
                root,
                UNCHECKED
            )

        finally:

            self._updating_checks = False

        self._update_selected_count()

    # ======================================================================
    # SELECTED LAYERS
    # ======================================================================

    def selected_layers(self):

        layers = []

        def walk(item):

            layer_id = item.data(
                0,
                USER_ROLE
            )

            if (
                layer_id
                and item.checkState(0)
                == CHECKED
            ):

                layer = (
                    QgsProject.instance()
                    .mapLayer(
                        layer_id
                    )
                )

                if layer is not None:

                    layers.append(
                        layer
                    )

            for i in range(
                item.childCount()
            ):

                walk(
                    item.child(i)
                )

        root = (
            self.layerTree
            .invisibleRootItem()
        )

        walk(root)

        return layers

    # ======================================================================
    # SELECTED COUNT
    # ======================================================================

    def _update_selected_count(self):

        try:

            count = len(
                self.selected_layers()
            )

            self.lblSelected.setText(
                f"Selected layers: {count}"
            )

        except Exception:

            self.lblSelected.setText(
                "Selected layers: 0"
            )

    # ======================================================================
    # VISIBLE FILTER
    # ======================================================================

    def _visible_filter_changed(
        self,
        checked
    ):

        self.populate_tree(
            preserve_selection=True
        )

    # ======================================================================
    # EXPORT
    # ======================================================================

    def export_clicked(self):

        layers = self.selected_layers()

        # --------------------------------------------------------------
        # Validate selection
        # --------------------------------------------------------------

        if not layers:

            QMessageBox.warning(
                self,
                "No Layers Selected",
                "Please select at least one "
                "PostgreSQL/PostGIS layer."
            )

            return

        # --------------------------------------------------------------
        # Validate output folder
        # --------------------------------------------------------------

        output_folder = (
            self.outputEdit
            .text()
            .strip()
        )

        if not output_folder:

            QMessageBox.warning(
                self,
                "Output Folder",
                "Please choose an output folder."
            )

            return

        if not os.path.isdir(
            output_folder
        ):

            QMessageBox.warning(
                self,
                "Invalid Folder",
                "The selected output folder "
                "does not exist."
            )

            return

        # ==================================================================
        # CONFIRMATION
        # ==================================================================

        reply = QMessageBox.question(
            self,
            "Confirm Export",
            "Export the selected PostgreSQL/PostGIS "
            f"layers?\n\n"
            f"Layers selected: {len(layers)}\n\n"
            f"Output folder:\n{output_folder}",
            MSG_YES | MSG_NO,
            MSG_YES
        )

        if reply != MSG_YES:

            return

        # ==================================================================
        # DISABLE CONTROLS
        # ==================================================================

        controls = [
            self.exportBtn,
            self.closeBtn,
            self.browseBtn,
            self.refreshBtn,
            self.selectAllBtn,
            self.clearAllBtn
        ]

        for widget in controls:

            widget.setEnabled(
                False
            )

        self.progress.setValue(
            0
        )

        self.statusLabel.setText(
            "Starting export..."
        )

        # ==================================================================
        # EXPORT
        # ==================================================================

        try:

            exporter = ExportEngine(
                self
            )

            result = exporter.export(
                layers,
                output_folder
            )

            # --------------------------------------------------------------
            # New ExportEngine result
            # --------------------------------------------------------------

            if isinstance(
                result,
                dict
            ):

                export_dir = result.get(
                    "export_dir",
                    ""
                )

                gpkg_path = result.get(
                    "gpkg_path",
                    ""
                )

                qgz_path = result.get(
                    "qgz_path",
                    None
                )

                log_path = result.get(
                    "log_path",
                    ""
                )

                successful_layers = result.get(
                    "successful",
                    []
                )

                failed_layers = result.get(
                    "failed",
                    []
                )

            # --------------------------------------------------------------
            # Old ExportEngine compatibility
            # --------------------------------------------------------------

            else:

                export_dir = str(
                    result
                )

                gpkg_path = ""

                qgz_path = None

                log_path = ""

                successful_layers = layers

                failed_layers = []

            # --------------------------------------------------------------
            # Progress
            # --------------------------------------------------------------

            self.progress.setValue(
                100
            )

            # =================================================================
            # PARTIAL SUCCESS
            # =================================================================

            if failed_layers:

                self.statusLabel.setText(
                    "Export completed with errors."
                )

                failed_text = "\n".join(
                    f"• {layer.name()}: {error}"
                    for layer, error
                    in failed_layers
                )

                message = (
                    "PG Exporter Pro completed with "
                    "some errors.\n\n"
                    f"Successful layers: "
                    f"{len(successful_layers)}\n"
                    f"Failed layers: "
                    f"{len(failed_layers)}\n\n"
                    f"Output folder:\n"
                    f"{export_dir}\n\n"
                    f"GeoPackage:\n"
                    f"{gpkg_path or 'Not available'}\n\n"
                    f"Export log:\n"
                    f"{log_path or 'Not available'}\n\n"
                    "Failed layers:\n"
                    f"{failed_text}"
                )

                QMessageBox.warning(
                    self,
                    "Export Completed With Errors",
                    message
                )

            # =================================================================
            # COMPLETE SUCCESS
            # =================================================================

            else:

                self.statusLabel.setText(
                    "Export completed successfully."
                )

                qgz_text = (
                    qgz_path
                    if qgz_path
                    else "Not created"
                )

                message = (
                    "PG Exporter Pro finished successfully.\n\n"
                    f"Layers exported: "
                    f"{len(successful_layers)}\n\n"
                    f"Output folder:\n"
                    f"{export_dir}\n\n"
                    f"GeoPackage:\n"
                    f"{gpkg_path or 'Not available'}\n\n"
                    f"Offline QGIS project:\n"
                    f"{qgz_text}\n\n"
                    f"Export log:\n"
                    f"{log_path or 'Not available'}"
                )

                QMessageBox.information(
                    self,
                    "Export Complete",
                    message
                )

        # ==================================================================
        # ERROR
        # ==================================================================

        except Exception as error:

            self.progress.setValue(
                0
            )

            self.statusLabel.setText(
                "Export failed."
            )

            QMessageBox.critical(
                self,
                "Export Failed",
                "The export could not be completed.\n\n"
                f"{error}"
            )

        # ==================================================================
        # RE-ENABLE
        # ==================================================================

        finally:

            for widget in controls:

                widget.setEnabled(
                    True
                )

            self._update_selected_count()