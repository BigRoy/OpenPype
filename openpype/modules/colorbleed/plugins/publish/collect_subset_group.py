import pyblish.api
from openpype.lib import TextDef
from openpype.pipeline.publish import OpenPypePyblishPluginMixin


class CollectUserSubsetGroup(pyblish.api.InstancePlugin,
                             OpenPypePyblishPluginMixin):
    """Allow user to define `subsetGroup` on publish in new publisher"""

    order = pyblish.api.CollectorOrder + 0.499
    label = "Collect User Subset Group"

    def process(self, instance):

        attr_values = self.get_attr_values_from_data(instance.data)
        user_subset_group = attr_values.get("subsetGroup", "").strip()
        if not user_subset_group:
            # Do nothing
            return

        if instance.data.get("subsetGroup"):
            self.log.warning(
                "User defined subset group '{}' is not applied because "
                "publisher had already collected subset group '{}'".format(
                    user_subset_group,
                    instance.data["subsetGroup"]
                )
            )
            return

        self.log.debug("Setting subset group: {}".format(user_subset_group))
        instance.data["subsetGroup"] = user_subset_group

    @classmethod
    def get_attribute_defs(cls):
        return [
            TextDef(
                "subsetGroup",
                label="Subset Group",
                placeholder="User defined subset group, e.g. 'Technical'",
                tooltip="User defined subset group, e.g. 'Technical'."
                        " This does nothing when empty.",
                default=""
            )
        ]
