# -*- coding: utf-8 -*-
import pyblish.api
from openpype.lib import EnumDef
from openpype.pipeline.publish import OpenPypePyblishPluginMixin
from openpype.modules.deadline.deadline_module import DeadlineModule


class CollectDeadlinePools(pyblish.api.InstancePlugin,
                           OpenPypePyblishPluginMixin):
    """Collect pools from instance or Publisher attributes, from Setting
    otherwise.

    Pools are used to control which DL workers could render the job.

    Pools might be set:
    - directly on the instance (set directly in DCC)
    - from Publisher attributes
    - from defaults from Settings.

    Publisher attributes could be shown even for instances that should be
    rendered locally as visibility is driven by product type of the instance
    (which will be `render` most likely).
    (Might be resolved in the future and class attribute 'families' should
    be cleaned up.)

    """

    order = pyblish.api.CollectorOrder + 0.420
    label = "Collect Deadline Pools"
    hosts = ["aftereffects",
             "fusion",
             "harmony"
             "nuke",
             "maya",
             "max"]

    families = ["render",
                "rendering",
                "render.farm",
                "renderFarm",
                "renderlayer",
                "maxrender"]

    primary_pool = None
    secondary_pool = None
    available_pools = []

    @classmethod
    def apply_settings(cls, project_settings, system_settings):
        # deadline.publish.CollectDeadlinePools
        settings = project_settings["deadline"]["publish"]["CollectDeadlinePools"]  # noqa
        cls.primary_pool = settings.get("primary_pool", None)
        cls.secondary_pool = settings.get("secondary_pool", None)

        deadline_url = (
            system_settings["modules"]["deadline"]["deadline_urls"]["default"]
        )
        cls.available_pools = DeadlineModule.get_deadline_pools_cached(
            deadline_url, log=cls.log
        )

    def process(self, instance):
        attr_values = self.get_attr_values_from_data(instance.data)
        if not instance.data.get("primaryPool"):
            instance.data["primaryPool"] = (
                attr_values.get("primaryPool") or self.primary_pool or "none"
            )
        if instance.data["primaryPool"] == "-":
            instance.data["primaryPool"] = None

        if not instance.data.get("secondaryPool"):
            instance.data["secondaryPool"] = (
                attr_values.get("secondaryPool") or self.secondary_pool or ""
            )

        if instance.data["secondaryPool"] == "-":
            instance.data["secondaryPool"] = None

    @classmethod
    def get_attribute_defs(cls):
        # Colorbleed edit: We don't use differing deadline URLs which means
        # we always know which URL we want to query for the available pools.
        # So we can use EnumDef instead of TextDef.
        # As such we retrieve available pools during `apply_settings`
        pools = [""] + sorted(cls.available_pools)
        return [
            EnumDef("primaryPool",
                    label="Primary Pool",
                    items=pools,
                    default=cls.primary_pool,
                    tooltip="Deadline primary pool, "
                            "applicable for farm rendering"),
            EnumDef("secondaryPool",
                    label="Secondary Pool",
                    items=pools,
                    default=cls.secondary_pool,
                    tooltip="Deadline secondary pool, "
                            "applicable for farm rendering")
        ]
