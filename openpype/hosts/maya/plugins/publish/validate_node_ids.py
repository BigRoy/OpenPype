import pyblish.api

from openpype.pipeline.publish import (
    ValidatePipelineOrder,
    PublishXmlValidationError,
    OpenPypePyblishPluginMixin
)
import openpype.hosts.maya.api.action
from openpype.hosts.maya.api import lib


class ValidateNodeIDs(pyblish.api.InstancePlugin):
    """Validate nodes have a Colorbleed Id.

    When IDs are missing from nodes *save your scene* and they should be
    automatically generated because IDs are created on non-referenced nodes
    in Maya upon scene save.

    """

    order = ValidatePipelineOrder
    label = 'Instance Nodes Have ID'
    hosts = ['maya']
    families = ["model",
                "look",
                "rig",
                "pointcache",
                "animation",
                "yetiRig",
                "assembly"]

    actions = [openpype.hosts.maya.api.action.SelectInvalidAction,
               openpype.hosts.maya.api.action.GenerateUUIDsOnInvalidAction]

    @classmethod
    def apply_settings(cls, project_settings):
        # Disable plug-in if cbId workflow is disabled
        if not project_settings["maya"].get("use_cbid_workflow", True):
            cls.enabled = False
            return

    def process(self, instance):
        """Process all meshes"""

        # Ensure all nodes have a cbId
        invalid = self.get_invalid(instance)
        if invalid:
            names = "\n".join(
                "- {}".format(node) for node in invalid
            )
            raise PublishXmlValidationError(
                plugin=self,
                message="Nodes found without IDs: {}".format(invalid),
                formatting_data={"nodes": names}
            )

    @classmethod
    def get_invalid(cls, instance):
        """Return the member nodes that are invalid"""

        # We do want to check the referenced nodes as it might be
        # part of the end product.
        id_nodes = lib.get_id_required_nodes(referenced_nodes=True,
                                             nodes=instance[:],
                                             # Exclude those with already
                                             # existing ids
                                             existing_ids=False)
        return id_nodes
