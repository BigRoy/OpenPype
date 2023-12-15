from collections import defaultdict

import pyblish.api
from openpype.pipeline.publish import (
    PublishValidationError,
    OptionalPyblishPluginMixin
)
import openpype.hosts.blender.api.action
from openpype.hosts.blender.api.cbid import get_id, get_id_required_nodes


class ValidateBlenderNodeIdsUnique(pyblish.api.InstancePlugin,
                                   OptionalPyblishPluginMixin):
    """Validate the nodes in the instance have a unique Colorbleed Id

    Here we ensure that what has been added to the instance is unique
    """

    order = pyblish.api.ValidatorOrder
    label = 'Non Duplicate Instance Members (ID)'
    hosts = ['blender']
    families = ["model"]

    actions = [openpype.hosts.blender.api.action.SelectInvalidAction,
               openpype.hosts.blender.api.action.GenerateUUIDsOnInvalidAction]

    def process(self, instance):
        """Process all meshes"""
        if not self.is_active(instance.data):
            return

        # Ensure all nodes have a cbId
        invalid = self.get_invalid(instance)
        if invalid:
            label = "Nodes found with non-unique asset IDs"

            invalid = [obj.name for obj in invalid]
            invalid.sort()

            raise PublishValidationError(
                message="{}, see log".format(label),
                title="Non-unique asset ids on nodes",
                description="{}\n- {}".format(label, "\n- ".join(invalid))
            )

    @classmethod
    def get_invalid(cls, instance):
        """Return the member nodes that are invalid"""

        instance_members = get_id_required_nodes(instance)

        # Collect each id with their members
        ids = defaultdict(list)
        for member in instance_members:
            object_id = get_id(member)
            if not object_id:
                continue
            ids[object_id].append(member)

        # Take only the ids with more than one member
        invalid = []
        for _ids, members in ids.items():
            if len(members) > 1:
                names = [obj.name for obj in members]
                members_text = "\n".join(
                    "- {}".format(name) for name in sorted(names)
                )
                cls.log.error(
                    "ID found on multiple nodes:\n{}".format(members_text)
                )
                invalid.extend(members)

        return invalid
