from collections import defaultdict
import pyblish.api

import openpype.hosts.blender.api.action
from openpype.hosts.blender.api.cbid import get_id, get_id_required_nodes
from openpype.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError,
    ValidatePipelineOrder
)
from openpype.client import get_assets


class ValidateBlenderNodeIDsRelated(pyblish.api.InstancePlugin,
                                    OptionalPyblishPluginMixin):
    """Validate nodes have a related Colorbleed Id to the instance.data[asset]

    """

    order = ValidatePipelineOrder
    label = 'Node Ids Related (ID)'
    hosts = ['blender']
    families = ["model"]
    optional = True

    actions = [openpype.hosts.blender.api.action.SelectInvalidAction,
               openpype.hosts.blender.api.action.GenerateUUIDsOnInvalidAction]

    def process(self, instance):
        """Process all nodes in instance (including hierarchy)"""
        if not self.is_active(instance.data):
            return

        # Ensure all nodes have a cbId
        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                message=(
                    "Node IDs found that are not related to asset: "
                    "{}".format(instance.data['asset'])
                ),
                description=(
                    "## Found nodes related to other assets\n"
                    "Detected nodes in your publish that are related to "
                    "other assets."
                )
            )

    @classmethod
    def get_invalid(cls, instance):
        """Return the member nodes that are invalid"""

        asset_id = str(instance.data['assetEntity']["_id"])

        # We do want to check the referenced nodes as it might be
        # part of the end product
        invalid = list()
        nodes_by_other_asset_ids = defaultdict(set)
        id_required_nodes = get_id_required_nodes(instance)
        for node in id_required_nodes:

            _id = get_id(node)
            if not _id:
                continue

            node_asset_id = _id.split(":", 1)[0]
            if node_asset_id != asset_id:
                invalid.append(node)
                nodes_by_other_asset_ids[node_asset_id].add(node)

        # Log what other assets were found.
        if nodes_by_other_asset_ids:
            project_name = instance.context.data["projectName"]
            other_asset_ids = list(nodes_by_other_asset_ids.keys())
            asset_docs = get_assets(project_name=project_name,
                                    asset_ids=other_asset_ids,
                                    fields=["name"])
            if asset_docs:
                # Log names of other assets detected
                # We disregard logging nodes/ids for asset ids where no asset
                # was found in the database because ValidateNodeIdsInDatabase
                # takes care of that.
                asset_names = {doc["name"] for doc in asset_docs}
                cls.log.error(
                    "Found nodes related to other assets: {}"
                    .format(", ".join(sorted(asset_names)))
                )

        return invalid