import pyblish.api

import openpype.hosts.maya.api.action
from openpype.client import get_assets
from openpype.hosts.maya.api import lib
from openpype.pipeline.publish import (
    PublishValidationError,
    ValidatePipelineOrder
)


class ValidateNodeIdsInDatabase(pyblish.api.InstancePlugin):
    """Validate if the CB Id is related to an asset in the database

    All nodes with the `cbId` attribute will be validated to ensure that
    the loaded asset in the scene is related to the current project.

    Tip: If there is an asset which is being reused from a different project
    please ensure the asset is republished in the new project

    """

    order = ValidatePipelineOrder
    label = 'Node Ids in Database'
    hosts = ['maya']
    families = ["*"]

    actions = [openpype.hosts.maya.api.action.SelectInvalidAction,
               openpype.hosts.maya.api.action.GenerateUUIDsOnInvalidAction]

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                ("Found asset IDs which are not related to "
                 "current project in instance: `{}`").format(instance.name))

    @classmethod
    def get_invalid(cls, instance):

        nodes = instance[:]
        if not nodes:
            return

        invalid = []

        # Get all id required nodes
        id_required_nodes = lib.get_id_required_nodes(referenced_nodes=False,
                                                      nodes=nodes)
        if not id_required_nodes:
            return

        db_asset_ids = cls._get_project_asset_ids(instance)

        # Get all asset IDs
        for node in id_required_nodes:
            cb_id = lib.get_id(node)

            # Ignore nodes without id, those are validated elsewhere
            if not cb_id:
                continue

            asset_id = cb_id.split(":", 1)[0]
            if asset_id not in db_asset_ids:
                cls.log.error("`%s` has unassociated asset ID" % node)
                invalid.append(node)

        return invalid

    @classmethod
    def _get_project_asset_ids(cls, instance):
        # We query the database only for the first instance instead of
        # per instance by storing a cache in the context
        context = instance.context
        key = "__cache_project_asset_ids_str"
        if key in context.data:
            return context.data[key]

        # check ids against database
        project_name = context.data["projectName"]
        asset_docs = get_assets(project_name, fields=["_id"])
        db_asset_ids = {
            str(asset_doc["_id"])
            for asset_doc in asset_docs
        }

        context.data[key] = db_asset_ids
        return db_asset_ids
