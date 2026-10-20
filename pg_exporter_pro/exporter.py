# -*- coding: utf-8 -*-

"""
/***************************************************************************
 PG Exporter Pro - Export Engine

 Exports selected PostgreSQL/PostGIS layers into:

    - One GeoPackage
    - QML styles
    - Export log
    - Offline QGIS project

 Compatible with QGIS 3.22+ / QGIS 4.x.

 IMPORTANT:
 - Source CRS is preserved.
 - No EPSG:4326 reprojection is requested.
 - Duplicate source field names are automatically renamed
   in the GeoPackage so all attributes can be exported.
 ***************************************************************************/
"""

import os
import re
import traceback

from qgis.PyQt.QtWidgets import QApplication

from qgis.core import (
    QgsProject,
    QgsVectorFileWriter
)

from .project_builder import ProjectBuilder


class ExportEngine:
    """Main PostgreSQL/PostGIS export engine."""

    def __init__(self, dialog):
        self.dialog = dialog

    # ==================================================================
    # PUBLIC EXPORT
    # ==================================================================

    def export(self, layers, output_folder):

        if not layers:
            raise RuntimeError(
                "No layers were selected for export."
            )

        if not output_folder:
            raise RuntimeError(
                "Output folder was not specified."
            )

        if not os.path.isdir(output_folder):
            raise RuntimeError(
                "Output folder does not exist:\n"
                f"{output_folder}"
            )

        project = QgsProject.instance()

        # --------------------------------------------------------------
        # Project name
        # --------------------------------------------------------------

        project_name = (
            project.baseName().strip()
            or "PG_Export"
        )

        project_name = self._safe_filename(
            project_name
        )

        # --------------------------------------------------------------
        # Prevent duplicate output directory
        #
        # Example:
        # output_folder =
        # D:/Exports/vancouver_lacamas
        #
        # project name =
        # vancouver_lacamas
        #
        # We should use output_folder directly rather than creating:
        # D:/Exports/vancouver_lacamas/vancouver_lacamas
        # --------------------------------------------------------------

        if (
            os.path.basename(
                os.path.normpath(
                    output_folder
                )
            ).lower()
            == project_name.lower()
        ):

            export_dir = output_folder

        else:

            export_dir = os.path.join(
                output_folder,
                project_name
            )

        styles_dir = os.path.join(
            export_dir,
            "styles"
        )

        os.makedirs(
            export_dir,
            exist_ok=True
        )

        os.makedirs(
            styles_dir,
            exist_ok=True
        )

        gpkg_path = os.path.join(
            export_dir,
            f"{project_name}.gpkg"
        )

        log_path = os.path.join(
            export_dir,
            "export_log.txt"
        )

        # --------------------------------------------------------------
        # Progress
        # --------------------------------------------------------------

        self._set_progress(0)
        self._set_status(
            "Preparing export..."
        )

        QApplication.processEvents()

        successful_layers = []
        failed_layers = []

        total = len(layers)

        # ==================================================================
        # LOG
        # ==================================================================

        with open(
            log_path,
            "w",
            encoding="utf-8"
        ) as log:

            log.write(
                "PG Exporter Pro - Export Log\n"
            )

            log.write(
                "=" * 70 + "\n\n"
            )

            log.write(
                f"Project       : {project_name}\n"
            )

            log.write(
                f"Layer count   : {total}\n"
            )

            log.write(
                f"Output folder : {export_dir}\n"
            )

            # ----------------------------------------------------------
            # Project CRS
            # ----------------------------------------------------------

            project_crs = project.crs()

            if project_crs.isValid():

                log.write(
                    f"Project CRS   : "
                    f"{project_crs.authid()} - "
                    f"{project_crs.description()}\n"
                )

            else:

                log.write(
                    "Project CRS   : Unknown\n"
                )

            log.write("\n")

            # ==========================================================
            # EXPORT LAYERS
            # ==========================================================

            for index, layer in enumerate(
                layers,
                start=1
            ):

                layer_name = layer.name()

                self._set_status(
                    f"Exporting {layer_name} "
                    f"({index}/{total})..."
                )

                QApplication.processEvents()

                try:

                    # --------------------------------------------------
                    # Validation
                    # --------------------------------------------------

                    if not layer.isValid():

                        raise RuntimeError(
                            "Layer is invalid."
                        )

                    if layer.providerType() != "postgres":

                        raise RuntimeError(
                            "Layer is not PostgreSQL/PostGIS."
                        )

                    # --------------------------------------------------
                    # CRS
                    # --------------------------------------------------

                    source_crs = layer.crs()

                    if source_crs.isValid():

                        log.write(
                            f"Layer: {layer_name}\n"
                        )

                        log.write(
                            f"  Source CRS: "
                            f"{source_crs.authid()} - "
                            f"{source_crs.description()}\n"
                        )

                    # --------------------------------------------------
                    # Check duplicate fields
                    # --------------------------------------------------

                    duplicate_fields = (
                        self._find_duplicate_fields(
                            layer
                        )
                    )

                    if duplicate_fields:

                        log.write(
                            "  Duplicate fields detected:\n"
                        )

                        for field_name in duplicate_fields:

                            log.write(
                                f"    - {field_name}\n"
                            )

                        log.write(
                            "  Duplicate fields will be renamed "
                            "in the GeoPackage.\n"
                        )

                    # --------------------------------------------------
                    # Export
                    # --------------------------------------------------

                    self._export_layer(
                        layer,
                        gpkg_path
                    )

                    # --------------------------------------------------
                    # Style
                    # --------------------------------------------------

                    style_saved = False

                    if (
                        hasattr(
                            self.dialog,
                            "chkStyles"
                        )
                        and self.dialog.chkStyles.isChecked()
                    ):

                        style_saved = (
                            self._save_style(
                                layer,
                                styles_dir
                            )
                        )

                    # --------------------------------------------------
                    # Feature count
                    # --------------------------------------------------

                    try:

                        feature_count = (
                            layer.featureCount()
                        )

                    except Exception:

                        feature_count = -1

                    # --------------------------------------------------
                    # Success
                    # --------------------------------------------------

                    successful_layers.append(
                        layer
                    )

                    log.write(
                        "  Status: SUCCESS\n"
                    )

                    log.write(
                        f"  Features: "
                        f"{feature_count}\n"
                    )

                    log.write(
                        "  Style: "
                        f"{'Saved' if style_saved else 'Skipped'}\n"
                    )

                    log.write("\n")

                except Exception as error:

                    failed_layers.append(
                        (
                            layer,
                            str(error)
                        )
                    )

                    log.write(
                        f"Layer: {layer_name}\n"
                    )

                    log.write(
                        "  Status: FAILED\n"
                    )

                    log.write(
                        f"  Error: {error}\n"
                    )

                    log.write("\n")

                    traceback.print_exc()

                # ------------------------------------------------------
                # Progress
                # ------------------------------------------------------

                progress = int(
                    index * 90 / total
                )

                self._set_progress(
                    progress
                )

                QApplication.processEvents()

            # ==========================================================
            # SUMMARY
            # ==========================================================

            log.write(
                "=" * 70 + "\n"
            )

            log.write(
                "EXPORT SUMMARY\n"
            )

            log.write(
                f"Successful : "
                f"{len(successful_layers)}\n"
            )

            log.write(
                f"Failed     : "
                f"{len(failed_layers)}\n"
            )

            log.write(
                f"Total      : "
                f"{total}\n"
            )

            log.write("\n")

            if failed_layers:

                log.write(
                    "FAILED LAYERS\n"
                )

                for layer, error in failed_layers:

                    log.write(
                        f"- {layer.name()}\n"
                    )

                    log.write(
                        f"  {error}\n"
                    )

                log.write("\n")

        # ==================================================================
        # NO SUCCESS
        # ==================================================================

        if not successful_layers:

            self._set_progress(0)

            self._set_status(
                "Export failed."
            )

            raise RuntimeError(
                "No layers could be exported.\n\n"
                f"See the export log:\n{log_path}"
            )

        # ==================================================================
        # BUILD OFFLINE PROJECT
        # ==================================================================

        qgz_path = None

        hierarchy_enabled = True

        if hasattr(
            self.dialog,
            "chkHierarchy"
        ):

            hierarchy_enabled = (
                self.dialog.chkHierarchy.isChecked()
            )

        if hierarchy_enabled:

            self._set_status(
                "Building offline QGIS project..."
            )

            QApplication.processEvents()

            try:

                builder = ProjectBuilder()

                qgz_path = builder.build(
                    project,
                    gpkg_path,
                    styles_dir,
                    export_dir,
                    selected_layers=successful_layers
                )

            except TypeError:

                # Backward compatibility if the current
                # ProjectBuilder does not yet accept
                # selected_layers.

                qgz_path = builder.build(
                    project,
                    gpkg_path,
                    styles_dir,
                    export_dir
                )

            except Exception as error:

                with open(
                    log_path,
                    "a",
                    encoding="utf-8"
                ) as log:

                    log.write(
                        "\n"
                        "OFFLINE PROJECT ERROR\n"
                    )

                    log.write(
                        f"{error}\n"
                    )

                raise RuntimeError(
                    "Layers were exported, but the offline "
                    "QGIS project could not be created.\n\n"
                    f"GeoPackage:\n{gpkg_path}\n\n"
                    f"Project error:\n{error}"
                )

        # ==================================================================
        # FINAL STATUS
        # ==================================================================

        self._set_progress(100)

        if failed_layers:

            self._set_status(
                "Export finished with errors."
            )

        else:

            self._set_status(
                "Export completed successfully."
            )

        QApplication.processEvents()

        return {
            "export_dir": export_dir,
            "gpkg_path": gpkg_path,
            "qgz_path": qgz_path,
            "log_path": log_path,
            "successful": successful_layers,
            "failed": failed_layers
        }

    # ==================================================================
    # EXPORT SINGLE LAYER
    # ==================================================================

    def _export_layer(
        self,
        layer,
        gpkg_path
    ):
        """
        Export a PostgreSQL/PostGIS layer to GeoPackage.

        The native source CRS is preserved.

        Duplicate field names are renamed using
        SaveVectorOptions.attributesExportNames.
        """

        options = (
            QgsVectorFileWriter
            .SaveVectorOptions()
        )

        # --------------------------------------------------------------
        # Driver
        # --------------------------------------------------------------

        options.driverName = "GPKG"

        # --------------------------------------------------------------
        # Layer name
        # --------------------------------------------------------------

        options.layerName = (
            self._safe_layer_name(
                layer.name()
            )
        )

        # --------------------------------------------------------------
        # Existing file
        # --------------------------------------------------------------

        if os.path.exists(
            gpkg_path
        ):

            options.actionOnExistingFile = (
                QgsVectorFileWriter
                .CreateOrOverwriteLayer
            )

        else:

            options.actionOnExistingFile = (
                QgsVectorFileWriter
                .CreateOrOverwriteFile
            )

        # --------------------------------------------------------------
        # IMPORTANT:
        # Export all source fields explicitly.
        # --------------------------------------------------------------

        fields = layer.fields()

        try:

            all_attributes = (
                fields.allAttributesList()
            )

        except AttributeError:

            all_attributes = list(
                range(
                    fields.count()
                )
            )

        options.attributes = (
            all_attributes
        )

        # --------------------------------------------------------------
        # Create unique output field names.
        #
        # Example:
        #
        # ID
        # ID
        # Name
        #
        # becomes:
        #
        # ID
        # ID_2
        # Name
        # --------------------------------------------------------------

        export_names = (
            self._unique_field_names(
                fields,
                all_attributes
            )
        )

        options.attributesExportNames = (
            export_names
        )

        # --------------------------------------------------------------
        # CRS
        # --------------------------------------------------------------
        #
        # We intentionally DO NOT specify a destination CRS.
        #
        # SaveVectorOptions.ct remains invalid, meaning:
        # NO coordinate transformation is requested.
        #
        # EPSG:2285 stays EPSG:2285.
        # --------------------------------------------------------------

        transform_context = (
            layer.transformContext()
            if hasattr(
                layer,
                "transformContext"
            )
            else QgsProject.instance()
            .transformContext()
        )

        error_message = ""

        # --------------------------------------------------------------
        # Current writer API
        # --------------------------------------------------------------

        try:

            result = (
                QgsVectorFileWriter
                .writeAsVectorFormatV3(
                    layer,
                    gpkg_path,
                    transform_context,
                    options
                )
            )

        except TypeError:

            # Compatibility fallback for bindings
            # exposing the optional errorMessage argument.

            result = (
                QgsVectorFileWriter
                .writeAsVectorFormatV3(
                    layer,
                    gpkg_path,
                    transform_context,
                    options,
                    error_message
                )
            )

        # --------------------------------------------------------------
        # Parse result
        # --------------------------------------------------------------

        error_code = result

        if isinstance(
            result,
            tuple
        ):

            error_code = result[0]

            if len(result) > 1:

                error_message = (
                    result[1]
                    or ""
                )

        # --------------------------------------------------------------
        # Check
        # --------------------------------------------------------------

        if (
            error_code
            != QgsVectorFileWriter.NoError
        ):

            message = (
                f"Failed to export "
                f"'{layer.name()}'.\n"
                f"Writer error code: "
                f"{error_code}"
            )

            if error_message:

                message += (
                    f"\nDetails: "
                    f"{error_message}"
                )

            raise RuntimeError(
                message
            )

    # ==================================================================
    # FIND DUPLICATE FIELDS
    # ==================================================================

    def _find_duplicate_fields(
        self,
        layer
    ):

        counts = {}
        duplicates = []

        fields = layer.fields()

        for i in range(
            fields.count()
        ):

            name = fields.at(i).name()

            key = name.lower()

            counts[key] = (
                counts.get(key, 0)
                + 1
            )

        for i in range(
            fields.count()
        ):

            name = fields.at(i).name()

            if (
                counts.get(
                    name.lower(),
                    0
                )
                > 1
                and name
                not in duplicates
            ):

                duplicates.append(
                    name
                )

        return duplicates

    # ==================================================================
    # UNIQUE FIELD NAMES
    # ==================================================================

    def _unique_field_names(
        self,
        fields,
        attributes
    ):
        """
        Create unique export field names.

        The list is indexed by source field index because
        QgsVectorFileWriter uses attributesExportNames[idx].
        """

        names = []

        used = set()

        for i in range(
            fields.count()
        ):

            original = fields.at(i).name()

            clean = str(
                original
            ).strip()

            if not clean:

                clean = (
                    f"field_{i + 1}"
                )

            base = clean

            key = base.lower()

            counter = 2

            while key in used:

                candidate = (
                    f"{base}_{counter}"
                )

                key = candidate.lower()

                counter += 1

            used.add(key)

            names.append(
                clean
                if counter == 2
                else candidate
            )

        return names

    # ==================================================================
    # SAVE STYLE
    # ==================================================================

    def _save_style(
        self,
        layer,
        styles_dir
    ):

        safe_name = (
            self._safe_filename(
                layer.name()
            )
        )

        qml_path = os.path.join(
            styles_dir,
            f"{safe_name}.qml"
        )

        try:

            result = (
                layer.saveNamedStyle(
                    qml_path
                )
            )

            if isinstance(
                result,
                tuple
            ):

                return bool(
                    result[0]
                )

            return bool(
                result
            )

        except Exception:

            traceback.print_exc()

            return False

    # ==================================================================
    # SAFE FILE NAME
    # ==================================================================

    def _safe_filename(
        self,
        name
    ):

        if not name:

            return "layer"

        cleaned = re.sub(
            r'[<>:"/\\|?*]',
            "_",
            str(name)
        )

        cleaned = cleaned.rstrip(
            " ."
        )

        return (
            cleaned
            or "layer"
        )

    # ==================================================================
    # SAFE GPKG LAYER NAME
    # ==================================================================

    def _safe_layer_name(
        self,
        name
    ):

        if not name:

            return "layer"

        cleaned = re.sub(
            r"[\r\n\t]+",
            "_",
            str(name)
        )

        cleaned = cleaned.strip()

        return (
            cleaned
            or "layer"
        )

    # ==================================================================
    # PROGRESS
    # ==================================================================

    def _set_progress(
        self,
        value
    ):

        try:

            self.dialog.progress.setValue(
                max(
                    0,
                    min(
                        100,
                        int(value)
                    )
                )
            )

        except Exception:

            pass

    # ==================================================================
    # STATUS
    # ==================================================================

    def _set_status(
        self,
        message
    ):

        try:

            self.dialog.statusLabel.setText(
                message
            )

        except Exception:

            pass