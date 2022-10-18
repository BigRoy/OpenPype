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


class ValidateSceneUnknownNodes(pyblish.api.ContextPlugin):
    """Checks to see if there are any unknown nodes in the scene.

    This often happens if nodes from plug-ins are used but are not available
    on this machine.

    Note: Some studios use unknown nodes to store data on (as attributes)
        because it's a lightweight node.

    """

    order = ValidateContentsOrder
    hosts = ['maya']
    families = ["model", "rig", "mayaScene", "look", "renderlayer", "yetiRig"]
    optional = True
    label = "Unknown Nodes"
    actions = [SelectInvalidAction, RepairContextAction]

    @staticmethod
    def get_invalid(context):
        return cmds.ls(type='unknown')

    def process(self, context):
        """Process all the nodes in the instance"""

        invalid = self.get_invalid(context)
        if invalid:
            raise ValueError("Unknown nodes found: {0}".format(invalid))

    @classmethod
    def repair(cls, context):

        for node in cls.get_invalid(context):
            try:
                force_delete(node)
            except RuntimeError as exc:
                cls.log.error(exc)
