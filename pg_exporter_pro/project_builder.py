# -*- coding: utf-8 -*-

"""
/***************************************************************************
 PG Exporter Pro - Project Builder

 Creates an offline QGIS project from the exported GeoPackage.

 Features:
    - Preserves original project CRS
    - Preserves EPSG:2285 when used by the source project
    - Includes ONLY successfully exported/selected layers
    - Preserves group hierarchy
    - Preserves layer order
    - Preserves group visibility
    - Preserves layer visibility
    - Preserves group expanded/collapsed state
    - Loads exported QML styles
    - Creates an offline .qgz project

 Compatible with QGIS 3.x and QGIS 4.x.
 ***************************************************************************/
"""

import os
import re

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer
)


class ProjectBuilder:
    """Build an offline QGIS project from exported PostGIS layers."""

    def __init__(self):
        pass

    # ==================================================================
    # BUILD PROJECT
    # ==================================================================

    def build(
        self,
        original_project,
        gpkg_path,
        styles_dir,
        output_dir,
        selected_layers=None
    ):
        """
        Build an offline QGIS project.

        Parameters
        ----------
        original_project : QgsProject
            Original QGIS project.

        gpkg_path : str
            Path to exported GeoPackage.

        styles_dir : str
            Folder containing exported QML styles.

        output_dir : str
            Output directory.

        selected_layers : list, optional
            List of QgsMapLayer objects which were successfully exported.
            If supplied, ONLY these layers are included in the new project.

        Returns
        -------
        str
            Path to generated .qgz project.
        """

        # ==================================================================
        # VALIDATION
        # ==================================================================

        if original_project is None:

            raise RuntimeError(
                "Original QGIS project is not available."
            )

        if not gpkg_path:

            raise RuntimeError(
                "GeoPackage path was not supplied."
            )

        if not os.path.exists(gpkg_path):

            raise RuntimeError(
                "GeoPackage does not exist:\n"
                f"{gpkg_path}"
            )

        if not output_dir:

            raise RuntimeError(
                "Output directory was not supplied."
            )

        os.makedirs(
            output_dir,
            exist_ok=True
        )

        # ==================================================================
        # SELECTED LAYER IDS
        # ==================================================================

        selected_ids = None

        if selected_layers is not None:

            selected_ids = set()

            for layer in selected_layers:

                try:

                    selected_ids.add(
                        layer.id()
                    )

                except Exception:

                    pass

        # ==================================================================
        # CREATE NEW PROJECT
        # ==================================================================

        new_project = QgsProject()

        # ==================================================================
        # PRESERVE ORIGINAL PROJECT CRS
        # ==================================================================

        original_crs = original_project.crs()

        if original_crs.isValid():

            new_project.setCrs(
                original_crs
            )

        # ==================================================================
        # PRESERVE PROJECT SETTINGS
        # ==================================================================

        try:

            new_project.setEllipsoid(
                original_project.ellipsoid()
            )

        except Exception:

            pass

        try:

            new_project.setDistanceUnits(
                original_project.distanceUnits()
            )

        except Exception:

            pass

        try:

            new_project.setAreaUnits(
                original_project.areaUnits()
            )

        except Exception:

            pass

        # ==================================================================
        # PROJECT TITLE / NAME
        # ==================================================================

        project_name = (
            original_project
            .baseName()
            .strip()
        )

        if not project_name:

            project_name = "PG_Export"

        project_name = self._safe_filename(
            project_name
        )

        try:

            original_title = (
                original_project
                .title()
            )

            if original_title:

                new_project.setTitle(
                    original_title
                )

        except Exception:

            pass

        # ==================================================================
        # ROOT NODE
        # ==================================================================

        new_root = (
            new_project
            .layerTreeRoot()
        )

        # ==================================================================
        # COPY TREE
        # ==================================================================

        self._copy_tree(
            source_node=(
                original_project
                .layerTreeRoot()
            ),
            target_node=new_root,
            gpkg_path=gpkg_path,
            styles_dir=styles_dir,
            project=new_project,
            selected_ids=selected_ids
        )

        # ==================================================================
        # OUTPUT PROJECT
        # ==================================================================

        qgz_path = os.path.join(
            output_dir,
            f"{project_name}.qgz"
        )

        # ==================================================================
        # WRITE PROJECT
        # ==================================================================

        success = new_project.write(
            qgz_path
        )

        if not success:

            raise RuntimeError(
                "Failed to create offline QGIS project:\n"
                f"{qgz_path}"
            )

        return qgz_path

    # ==================================================================
    # COPY TREE
    # ==================================================================

    def _copy_tree(
        self,
        source_node,
        target_node,
        gpkg_path,
        styles_dir,
        project,
        selected_ids=None
    ):
        """
        Recursively copy only selected PostgreSQL/PostGIS
        layers while maintaining the original hierarchy.
        """

        for child in source_node.children():

            # ==============================================================
            # GROUP
            # ==============================================================

            if isinstance(
                child,
                QgsLayerTreeGroup
            ):

                # ----------------------------------------------------------
                # Skip groups that contain no selected layers
                # ----------------------------------------------------------

                if not self._group_contains_selected(
                    child,
                    selected_ids
                ):

                    continue

                # ----------------------------------------------------------
                # Create group
                # ----------------------------------------------------------

                group = target_node.addGroup(
                    child.name()
                )

                # ----------------------------------------------------------
                # Preserve expanded state
                # ----------------------------------------------------------

                try:

                    group.setExpanded(
                        child.isExpanded()
                    )

                except Exception:

                    pass

                # ----------------------------------------------------------
                # Preserve group visibility
                # ----------------------------------------------------------

                try:

                    group.setItemVisibilityChecked(
                        child.itemVisibilityChecked()
                    )

                except Exception:

                    pass

                # ----------------------------------------------------------
                # Recursively copy contents
                # ----------------------------------------------------------

                self._copy_tree(
                    source_node=child,
                    target_node=group,
                    gpkg_path=gpkg_path,
                    styles_dir=styles_dir,
                    project=project,
                    selected_ids=selected_ids
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
                # PostgreSQL/PostGIS only
                # ----------------------------------------------------------

                if layer.providerType() != "postgres":

                    continue

                # ----------------------------------------------------------
                # If selected_ids was supplied, only use selected layers
                # ----------------------------------------------------------

                if (
                    selected_ids is not None
                    and layer.id() not in selected_ids
                ):

                    continue

                # ----------------------------------------------------------
                # Create offline layer
                # ----------------------------------------------------------

                offline_layer = (
                    self._create_offline_layer(
                        original_layer=layer,
                        gpkg_path=gpkg_path,
                        styles_dir=styles_dir
                    )
                )

                if offline_layer is None:

                    continue

                # ----------------------------------------------------------
                # Add to project without automatically placing at root
                # ----------------------------------------------------------

                project.addMapLayer(
                    offline_layer,
                    False
                )

                # ----------------------------------------------------------
                # Add to correct group/location
                # ----------------------------------------------------------

                target_layer_node = (
                    target_node.addLayer(
                        offline_layer
                    )
                )

                # ----------------------------------------------------------
                # Preserve layer visibility
                # ----------------------------------------------------------

                try:

                    target_layer_node.setItemVisibilityChecked(
                        child.itemVisibilityChecked()
                    )

                except Exception:

                    pass

                # ----------------------------------------------------------
                # Preserve custom properties where possible
                # ----------------------------------------------------------

                try:

                    original_props = (
                        child.customProperty(
                            "customProperty"
                        )
                    )

                    if original_props is not None:

                        target_layer_node.setCustomProperty(
                            "customProperty",
                            original_props
                        )

                except Exception:

                    pass

    # ==================================================================
    # CHECK GROUP FOR SELECTED LAYERS
    # ==================================================================

    def _group_contains_selected(
        self,
        group,
        selected_ids
    ):
        """
        Returns True when the group contains at least one
        selected PostgreSQL/PostGIS layer.
        """

        # --------------------------------------------------------------
        # When selected_ids is None, include PostgreSQL groups normally.
        # --------------------------------------------------------------

        if selected_ids is None:

            for child in group.children():

                if isinstance(
                    child,
                    QgsLayerTreeLayer
                ):

                    layer = child.layer()

                    if (
                        layer is not None
                        and layer.providerType()
                        == "postgres"
                    ):

                        return True

                elif isinstance(
                    child,
                    QgsLayerTreeGroup
                ):

                    if self._group_contains_selected(
                        child,
                        None
                    ):

                        return True

            return False

        # --------------------------------------------------------------
        # Selected IDs supplied
        # --------------------------------------------------------------

        for child in group.children():

            # ----------------------------------------------------------
            # Layer
            # ----------------------------------------------------------

            if isinstance(
                child,
                QgsLayerTreeLayer
            ):

                layer = child.layer()

                if layer is None:

                    continue

                if layer.providerType() != "postgres":

                    continue

                if layer.id() in selected_ids:

                    return True

            # ----------------------------------------------------------
            # Nested group
            # ----------------------------------------------------------

            elif isinstance(
                child,
                QgsLayerTreeGroup
            ):

                if self._group_contains_selected(
                    child,
                    selected_ids
                ):

                    return True

        return False

    # ==================================================================
    # CREATE OFFLINE LAYER
    # ==================================================================

    def _create_offline_layer(
        self,
        original_layer,
        gpkg_path,
        styles_dir
    ):
        """
        Create a local GeoPackage layer using the exported
        layer's actual name.
        """

        layer_name = (
            original_layer
            .name()
            .strip()
        )

        if not layer_name:

            return None

        # --------------------------------------------------------------
        # GeoPackage URI
        # --------------------------------------------------------------

        safe_layer_name = self._safe_layer_name(
            layer_name
        )

        uri = (
            f"{gpkg_path}"
            f"|layername={safe_layer_name}"
        )

        offline_layer = QgsVectorLayer(
            uri,
            layer_name,
            "ogr"
        )

        # --------------------------------------------------------------
        # Validate
        # --------------------------------------------------------------

        if not offline_layer.isValid():

            # ----------------------------------------------------------
            # Fallback: try the original layer name in case the writer
            # retained it exactly.
            # ----------------------------------------------------------

            if safe_layer_name != layer_name:

                fallback_uri = (
                    f"{gpkg_path}"
                    f"|layername={layer_name}"
                )

                fallback_layer = QgsVectorLayer(
                    fallback_uri,
                    layer_name,
                    "ogr"
                )

                if fallback_layer.isValid():

                    offline_layer = (
                        fallback_layer
                    )

                else:

                    return None

            else:

                return None

        # ==================================================================
        # CRS CHECK
        # ==================================================================

        try:

            source_crs = (
                original_layer.crs()
            )

            if source_crs.isValid():

                # ----------------------------------------------------------
                # IMPORTANT:
                # This does NOT reproject the data.
                # It only ensures the layer is associated with its
                # original CRS if the GeoPackage reports something else.
                # ----------------------------------------------------------

                if (
                    offline_layer.crs()
                    != source_crs
                ):

                    offline_layer.setCrs(
                        source_crs
                    )

        except Exception:

            pass

        # ==================================================================
        # LOAD QML STYLE
        # ==================================================================

        safe_style_name = (
            self._safe_filename(
                layer_name
            )
        )

        style_path = os.path.join(
            styles_dir,
            f"{safe_style_name}.qml"
        )

        if os.path.exists(
            style_path
        ):

            try:

                offline_layer.loadNamedStyle(
                    style_path
                )

            except Exception:

                pass

        # ==================================================================
        # REPAINT
        # ==================================================================

        try:

            offline_layer.triggerRepaint()

        except Exception:

            pass

        return offline_layer

    # ==================================================================
    # SAFE FILE NAME
    # ==================================================================

    def _safe_filename(
        self,
        name
    ):
        """
        Make a safe Windows filename.
        """

        if not name:

            return "layer"

        result = re.sub(
            r'[<>:"/\\|?*]',
            "_",
            str(name)
        )

        result = result.rstrip(
            " ."
        )

        if not result:

            return "layer"

        return result

    # ==================================================================
    # SAFE GPKG LAYER NAME
    # ==================================================================

    def _safe_layer_name(
        self,
        name
    ):
        """
        Keep the GeoPackage layer name compatible with
        the name produced by ExportEngine.
        """

        if not name:

            return "layer"

        result = re.sub(
            r"[\r\n\t]+",
            "_",
            str(name)
        )

        result = result.strip()

        if not result:

            return "layer"

        return result