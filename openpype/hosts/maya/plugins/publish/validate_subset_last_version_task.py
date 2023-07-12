import re
from collections import defaultdict

import pyblish.api

from openpype.client import (
    get_subsets,
    get_last_versions
)
from openpype.pipeline.publish import filter_instances_for_context_plugin


class ValidateSubsetsLastVersionTask(pyblish.api.InstancePlugin):
    """Validate if current publish matches last version's task.

    If a particular subset (e.g. "pointcacheEnv") for an asset previously came
    from a different task this will raise an error to avoid accidentally
    overwriting publishes from another task.

    You can disable the validator if you are certain you want to publish
    into the existing subsets. Once you have published a new version then
    the new version's task matches your current task and thus the next time
    this will not invalidate.

    """

    order = pyblish.api.ValidatorOrder
    label = 'Match task last published version'
    hosts = ['maya']
    families = ["animation", "pointcache"]
    optional = True

    # Cache shared between all instances
    cache = None

    def process(self, instance):

        task = instance.data.get("task") or instance.context.data.get("task")
        last_task = self.get_last_task_for_instance(instance)
        if not last_task:
            return

        if task != last_task:
            subset_name = instance.data["subset"]
            asset_name = instance.data["asset"]
            raise RuntimeError(
                "Last version of {} > {} was published "
                "from another task: {}. (current task: {})\n"
                "If you are sure this is what you want then you can disable "
                "the validator."
                "".format(asset_name, subset_name, last_task, task)
            )

    def populate_cache(self, context):
        """Populate cache to optimize the query for many instances

        On first run we cache this for all relevant instances in the context.
        """

        self.cache = {}

        # Confirm we are generating the subsets from the same task as before
        instances = list(
            filter_instances_for_context_plugin(plugin=self, context=context)
        )
        if not instances:
            return

        project_name = context.data["projectName"]

        # Get subset names per asset id for the instances
        subset_names_by_asset_ids = defaultdict(set)
        for instance in instances:
            asset_id = instance.data["assetEntity"]["_id"]
            subset_name = instance.data["subset"]
            subset_names_by_asset_ids[asset_id].add(subset_name)

        # Get the subsets
        subsets = list(get_subsets(
            project_name=project_name,
            names_by_asset_ids=subset_names_by_asset_ids,
            fields=["_id", "name", "parent"]
        ))
        if not subsets:
            return

        subset_ids = [subset["_id"] for subset in subsets]
        versions_by_subset_id = get_last_versions(
            project_name=project_name,
            subset_ids=subset_ids,
            fields=["parent", "data.source"]
        )
        if not versions_by_subset_id:
            return

        self.cache["version_by_asset_id_and_subset_name"] = {
            (subset["parent"], subset["name"]):
                versions_by_subset_id.get(subset["_id"]) for subset in subsets
        }

    def get_last_task_for_instance(self, instance):
        """Return task name of the last matching asset>subset instance"""

        if self.cache is None:
            self.populate_cache(instance.context)

        if not self.cache:
            # No relevant data at all (no existing subsets or versions)
            return

        asset_id = instance.data["assetEntity"]["_id"]
        subset_name = instance.data["subset"]
        version = self.cache["version_by_asset_id_and_subset_name"].get(
            (asset_id, subset_name)
        )
        if version is None:
            self.log.debug("No existing version for {}".format(subset_name))
            return

        # Since source task is not published along with the data we just
        # assume the task name from the root file path it was published from
        source = version.get("data", {}).get("source")
        if source is None:
            return

        # Assume workfile path matches /work/{task}/
        pattern = "/work/([^/]+)/"
        match = re.search(pattern, source)
        if match:
            return match.group(1)
