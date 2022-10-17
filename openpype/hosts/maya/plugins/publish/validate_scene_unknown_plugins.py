from maya import cmds

import pyblish.api
from openpype.hosts.maya.api.action import SelectInvalidAction
from openpype.pipeline.publish import (
    ValidateContentsOrder,
    RepairContextAction
)


def force_delete(node):
    if cmds.objExists(node):
        cmds.lockNode(node, lock=False)
        cmds.delete(node)


class ValidateSceneUnknownPlugins(pyblish.api.ContextPlugin):
    """Checks to see if there are any unknown plugins in the scene.

    This often happens if plug-in requirements were stored with the scene
    but those plug-ins are not available on the current machine.

    Repairing this will remove any trace of that particular plug-in.


    Note: Some studios use unknown nodes to store data on (as attributes)
        because it's a lightweight node.

    """

    order = ValidateContentsOrder
    hosts = ['maya']
    optional = True
    label = "Unknown Plug-ins"
    actions = [RepairContextAction]

    @staticmethod
    def get_invalid():
        return sorted(cmds.unknownPlugin(query=True, list=True) or [])

    def process(self, context):
        """Process all the nodes in the instance"""

        invalid = self.get_invalid()
        if invalid:
            raise ValueError(
                "{} unknown plug-ins found: {}".format(len(invalid), invalid))

    @classmethod
    def repair(cls, context):

        for plugin in cls.get_invalid():
            cls.log.debug("Removing unknown plugin: %s .." % plugin)

            node_types = cmds.unknownPlugin(plugin, query=True, nodeTypes=True)
            if node_types:
                for node in cmds.ls(type=node_types):
                    try:
                        force_delete(node)
                    except RuntimeError as exc:
                        cls.log.error(exc)

            # TODO: Remove datatypes
            # datatypes = cmds.unknownPlugin(plugin,
            #                                query=True, dataTypes=True)

            try:
                cmds.unknownPlugin(plugin, remove=True)
            except RuntimeError as exc:
                cls.log.warning(
                    "Failed to remove plug-in {}: {}".format(plugin, exc))