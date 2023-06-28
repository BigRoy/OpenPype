import pyblish.api

from openpype.pipeline.publish import OpenPypePyblishPluginMixin
from openpype.client import get_subset_by_name


class ValidateSubsetGroupChange(pyblish.api.InstancePlugin,
                                OpenPypePyblishPluginMixin):
    """Log a warning if `subsetGroup` changes from current subset's group"""

    order = pyblish.api.ValidatorOrder
    label = "Validate Subset Group Change"

    def process(self, instance):

        if not instance.data.get("subsetGroup"):
            return

        subset_group = instance.data["subsetGroup"]
        self.log.debug(
            "Instance has subset group set to: {}".format(subset_group)
        )

        asset_doc = instance.data.get("assetEntity")
        if not asset_doc:
            return

        subset_name = instance.data.get("subset")
        if not subset_name:
            return

        # Get existing subset if it exists
        project_name = instance.context.data["projectName"]
        existing_subset_doc = get_subset_by_name(
            project_name, subset_name, asset_doc["_id"],
            fields=["data.subsetGroup"]
        )
        if not existing_subset_doc:
            return

        existing_group = existing_subset_doc.get("data", {}).get("subsetGroup")
        if not existing_group:
            return

        if existing_group != subset_group:
            self.log.warning(
                "Subset group changes from `{}` to `{}`".format(
                    existing_group, subset_group
                )
            )
