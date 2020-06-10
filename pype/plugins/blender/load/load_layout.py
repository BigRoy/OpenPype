"""Load a layout in Blender."""

import logging
from pathlib import Path
from pprint import pformat
from typing import Dict, List, Optional

from avalon import api, blender
import bpy
import pype.hosts.blender.plugin


logger = logging.getLogger("pype").getChild(
    "blender").getChild("load_layout")


class BlendLayoutLoader(pype.hosts.blender.plugin.AssetLoader):
    """Load animations from a .blend file.

    Warning:
        Loading the same asset more then once is not properly supported at the
        moment.
    """

    families = ["layout"]
    representations = ["blend"]

    label = "Link Layout"
    icon = "code-fork"
    color = "orange"

    @staticmethod
    def _remove(self, objects, lib_container):

        for obj in objects:

            if obj.type == 'ARMATURE':
                bpy.data.armatures.remove(obj.data)
            elif obj.type == 'MESH':
                bpy.data.meshes.remove(obj.data)

        for element_container in bpy.data.collections[lib_container].children:
            for child in element_container.children:
                bpy.data.collections.remove(child)
            bpy.data.collections.remove(element_container)

        bpy.data.collections.remove(bpy.data.collections[lib_container])

    @staticmethod
    def _process(self, libpath, lib_container, container_name, actions):

        relative = bpy.context.preferences.filepaths.use_relative_paths
        with bpy.data.libraries.load(
            libpath, link=True, relative=relative
        ) as (_, data_to):
            data_to.collections = [lib_container]

        scene = bpy.context.scene

        scene.collection.children.link(bpy.data.collections[lib_container])

        layout_container = scene.collection.children[lib_container].make_local()

        meshes = []
        armatures = []

        objects_list = []

        for element_container in layout_container.children:
            element_container.make_local()
            armatures.extend([obj for obj in element_container.objects if obj.type == 'ARMATURE'])
            for child in element_container.children:
                child.make_local()
                meshes.extend(child.objects)

        # Link meshes first, then armatures.
        # The armature is unparented for all the non-local meshes,
        # when it is made local.
        for obj in meshes + armatures:
            obj = obj.make_local()
            obj.data.make_local()

            if not obj.get(blender.pipeline.AVALON_PROPERTY):
                obj[blender.pipeline.AVALON_PROPERTY] = dict()

            avalon_info = obj[blender.pipeline.AVALON_PROPERTY]
            avalon_info.update({"container_name": container_name})

            action = actions.get( obj.name, None )

            if obj.type == 'ARMATURE' and action is not None:
                obj.animation_data.action = action
            
            objects_list.append(obj)

        layout_container.pop(blender.pipeline.AVALON_PROPERTY)

        bpy.ops.object.select_all(action='DESELECT')

        return objects_list

    def process_asset(
        self, context: dict, name: str, namespace: Optional[str] = None,
        options: Optional[Dict] = None
    ) -> Optional[List]:
        """
        Arguments:
            name: Use pre-defined name
            namespace: Use pre-defined namespace
            context: Full parenthood of representation to load
            options: Additional settings dictionary
        """

        libpath = self.fname
        asset = context["asset"]["name"]
        subset = context["subset"]["name"]
        lib_container = pype.hosts.blender.plugin.asset_name(asset, subset)
        container_name = pype.hosts.blender.plugin.asset_name(
            asset, subset, namespace
        )

        container = bpy.data.collections.new(lib_container)
        container.name = container_name
        blender.pipeline.containerise_existing(
            container,
            name,
            namespace,
            context,
            self.__class__.__name__,
        )

        container_metadata = container.get(
            blender.pipeline.AVALON_PROPERTY)

        container_metadata["libpath"] = libpath
        container_metadata["lib_container"] = lib_container

        objects_list = self._process(
            self, libpath, lib_container, container_name, {})

        # Save the list of objects in the metadata container
        container_metadata["objects"] = objects_list

        nodes = list(container.objects)
        nodes.append(container)
        self[:] = nodes
        return nodes

    def update(self, container: Dict, representation: Dict):
        """Update the loaded asset.

        This will remove all objects of the current collection, load the new
        ones and add them to the collection.
        If the objects of the collection are used in another collection they
        will not be removed, only unlinked. Normally this should not be the
        case though.

        Warning:
            No nested collections are supported at the moment!
        """

        collection = bpy.data.collections.get(
            container["objectName"]
        )

        libpath = Path(api.get_representation_path(representation))
        extension = libpath.suffix.lower()

        logger.info(
            "Container: %s\nRepresentation: %s",
            pformat(container, indent=2),
            pformat(representation, indent=2),
        )

        assert collection, (
            f"The asset is not loaded: {container['objectName']}"
        )
        assert not (collection.children), (
            "Nested collections are not supported."
        )
        assert libpath, (
            "No existing library file found for {container['objectName']}"
        )
        assert libpath.is_file(), (
            f"The file doesn't exist: {libpath}"
        )
        assert extension in pype.hosts.blender.plugin.VALID_EXTENSIONS, (
            f"Unsupported file: {libpath}"
        )

        collection_metadata = collection.get(
            blender.pipeline.AVALON_PROPERTY)

        collection_libpath = collection_metadata["libpath"]
        normalized_collection_libpath = (
            str(Path(bpy.path.abspath(collection_libpath)).resolve())
        )
        normalized_libpath = (
            str(Path(bpy.path.abspath(str(libpath))).resolve())
        )
        logger.debug(
            "normalized_collection_libpath:\n  %s\nnormalized_libpath:\n  %s",
            normalized_collection_libpath,
            normalized_libpath,
        )
        if normalized_collection_libpath == normalized_libpath:
            logger.info("Library already loaded, not updating...")
            return

        objects = collection_metadata["objects"]
        lib_container = collection_metadata["lib_container"]

        actions = {}

        for obj in objects:

            if obj.type == 'ARMATURE':

                actions[obj.name] = obj.animation_data.action

        self._remove(self, objects, lib_container)

        objects_list = self._process(
            self, str(libpath), lib_container, collection.name, actions)

        # Save the list of objects in the metadata container
        collection_metadata["objects"] = objects_list
        collection_metadata["libpath"] = str(libpath)
        collection_metadata["representation"] = str(representation["_id"])

        bpy.ops.object.select_all(action='DESELECT')

    def remove(self, container: Dict) -> bool:
        """Remove an existing container from a Blender scene.

        Arguments:
            container (avalon-core:container-1.0): Container to remove,
                from `host.ls()`.

        Returns:
            bool: Whether the container was deleted.

        Warning:
            No nested collections are supported at the moment!
        """

        collection = bpy.data.collections.get(
            container["objectName"]
        )
        if not collection:
            return False
        assert not (collection.children), (
            "Nested collections are not supported."
        )

        collection_metadata = collection.get(
            blender.pipeline.AVALON_PROPERTY)
        objects = collection_metadata["objects"]
        lib_container = collection_metadata["lib_container"]

        self._remove(self, objects, lib_container)

        bpy.data.collections.remove(collection)

        return True
