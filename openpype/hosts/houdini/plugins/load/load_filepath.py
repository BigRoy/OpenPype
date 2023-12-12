import os
from openpype.pipeline import (
    load,
    get_representation_path,
)
from openpype.hosts.houdini.api import pipeline

import re
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
        filepath = self.format_path(
            path=self.filepath_from_context(context),
            representation=context["representation"]
        )
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
        file_path = self.format_path(
            path=get_representation_path(representation),
            representation=representation
        )

        node = container["node"]
        node.setParms({
            "filepath": file_path,
            "representation": str(representation["_id"])
        })

        # Update the parameter default value (cosmetics)
        parm_template_group = node.parmTemplateGroup()
        parm = parm_template_group.find("filepath")
        parm.setDefaultValue((file_path,))
        parm_template_group.replace(parm_template_group.find("filepath"),
                                    parm)
        node.setParmTemplateGroup(parm_template_group)

    def remove(self, container):

        node = container["node"]
        node.destroy()

    @staticmethod
    def format_path(path, representation):
        """Format file path for sequence with $F."""
        if not os.path.exists(path):
            raise RuntimeError("Path does not exist: %s" % path)

        # The path is either a single file or sequence in a folder.
        frame = representation["context"].get("frame")
        if frame is not None:
            # Substitute frame number in sequence with $F with padding
            ext = representation.get("ext", representation["name"])
            token = "$F{}".format(len(frame))   # e.g. $F4
            pattern = r"\.(\d+)\.{ext}$".format(ext=re.escape(ext))
            path = re.sub(pattern, ".{}.{}".format(token, ext), path)

        return os.path.normpath(path).replace("\\", "/")
