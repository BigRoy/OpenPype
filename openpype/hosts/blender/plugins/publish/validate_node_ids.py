import pyblish.api

from openpype.pipeline.publish import (
    ValidatePipelineOrder,
    PublishXmlValidationError
)
import openpype.hosts.blender.api.action
from openpype.hosts.blender.api.cbid import get_id, get_id_required_nodes


class ValidateBlenderNodeIDs(pyblish.api.InstancePlugin):
    """Validate nodes have a Colorbleed Id."""

    order = ValidatePipelineOrder
    label = 'Instance Nodes Have ID'
    hosts = ['blender']
    families = ["model"]

    actions = [openpype.hosts.blender.api.action.SelectInvalidAction,
               openpype.hosts.blender.api.action.GenerateUUIDsOnInvalidAction]

    def process(self, instance):
        """Process all meshes"""

        # Ensure all nodes have a cbId
        invalid = self.get_invalid(instance)
        if invalid:
            names = [obj.name_full for obj in invalid]
            names_list = "\n".join(
                "- {}".format(name) for name in names
            )
            raise PublishXmlValidationError(
                plugin=self,
                message="Nodes found without IDs: {}".format(names),
                formatting_data={"nodes": names_list}
            )

    @classmethod
    def get_invalid(cls, instance):
        """Return the member nodes that are invalid"""

        # Include meshes and curves
        id_required_nodes = get_id_required_nodes(instance)
        return [node for node in id_required_nodes if not get_id(node)]
