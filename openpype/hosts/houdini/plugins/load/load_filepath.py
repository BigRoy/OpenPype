import os
from openpype.pipeline import (
    load,
    get_representation_path,
)
from openpype.hosts.houdini.api import pipeline

import clique
import hou


class FilePathLoader(load.LoaderPlugin):
    """Load a managed filepath to a null node"""

    label = "Load filepath to node"
    order = 9
    icon = "link"
    color = "white"
    families = ["*"]
    representations = ["*"]

    def load(self, context, name=None, namespace=None, data=None):

        # Get the root node
        obj = hou.node("/obj")

        # Define node name
        namespace = namespace if namespace else context["asset"]["name"]
        node_name = "{}_{}".format(namespace, name) if namespace else name

        # Create a null node
        container = obj.createNode("null", node_name=node_name)

        # Destroy any children
        for node in container.children():
            node.destroy()

        # Add filepath attribute, set value as default value
        filepath = self.fname.replace("\\", "/")
        parm_template_group = container.parmTemplateGroup()
        attr_folder = hou.FolderParmTemplate("attributes_folder", "Attributes")
        parm = hou.StringParmTemplate(name="filepath",
                                      label="Filepath",
                                      num_components=1,
                                      default_value=(filepath,))
        attr_folder.addParmTemplate(parm)
        parm_template_group.append(attr_folder)

        # Hide some default labels
        for folder_label in ["Transform", "Render", "Misc", "Redshift OBJ"]:
            folder = parm_template_group.findFolder(folder_label)
            if not folder:
                continue
            parm_template_group.hideFolder(folder_label, True)

        container.setParmTemplateGroup(parm_template_group)

        container.setDisplayFlag(False)
        container.setSelectableInViewport(False)
        container.useXray(False)

        nodes = [container]

        self[:] = nodes

        return pipeline.containerise(
            node_name,
            namespace,
            nodes,
            context,
            self.__class__.__name__,
            suffix="",
        )

    def update(self, container, representation):

        # Update the file path
        file_path = get_representation_path(representation)

        node = container["node"]
        node.setParms({
            "filepath": self.format_path(file_path),
            "representation": str(representation["_id"])
        })

        # TODO: Update the parameter default value (cosmetics)

    def remove(self, container):

        node = container["node"]
        node.destroy()

    def format_path(self, path):
        """Format using $F{padding} token if sequence, otherwise just path."""

        # Find all frames in the folder
        _, ext = os.path.splitext(path)
        folder = os.path.dirname(path)
        frames = [f for f in os.listdir(folder) if f.endswith(ext)]

        # Get the collection of frames to detect frame padding
        patterns = [clique.PATTERNS["frames"]]
        collections, remainder = clique.assemble(frames,
                                                 minimum_items=1,
                                                 patterns=patterns)
        self.log.debug("Detected collections: {}".format(collections))
        self.log.debug("Detected remainder: {}".format(remainder))

        if not collections and remainder:
            if len(remainder) != 1:
                raise ValueError("Frames not correctly detected "
                                 "in: {}".format(remainder))

            # A single frame without frame range detected
            return os.path.normpath(path).replace("\\", "/")

        # Frames detected with a valid "frame" number pattern
        # Then we don't want to have any remainder files found
        assert len(collections) == 1 and not remainder
        collection = collections[0]

        num_frames = len(collection.indexes)
        if num_frames == 1:
            # Return the input path without dynamic $F variable
            result = path
        else:
            # More than a single frame detected - use $F{padding}
            fname = "{}$F{}{}".format(collection.head,
                                      collection.padding,
                                      collection.tail)
            result = os.path.join(folder, fname)

        # Format file name, Houdini only wants forward slashes
        return os.path.normpath(result).replace("\\", "/")
