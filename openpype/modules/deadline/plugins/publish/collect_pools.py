# -*- coding: utf-8 -*-
"""Collect Deadline pools. Choose default one from Settings

"""
import pyblish.api
from openpype.lib import EnumDef
from openpype.pipeline.publish import OpenPypePyblishPluginMixin
from openpype.modules.deadline.deadline_module import DeadlineModule


class CollectDeadlinePools(pyblish.api.InstancePlugin,
                           OpenPypePyblishPluginMixin):
    """Collect pools from instance if present, from Setting otherwise."""

    order = pyblish.api.CollectorOrder + 0.420
    label = "Collect Deadline Pools"
    families = ["rendering",
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

        if not hasattr(DeadlineModule, "_cache_available_pools"):
            # Secretly cache the pools on the DeadlineModule that way
            # we don't need to query deadline web service every time reset
            # This is fine since our Deadline pools are mostly static anyway
            # and otherwise we can request an artist to restart their DCCs
            deadline_url = (
                system_settings["modules"]
                               ["deadline"]
                               ["deadline_urls"]
                               ["default"]
            )
            available_pools = DeadlineModule.get_deadline_pools(deadline_url,
                                                                log=cls.log)
            DeadlineModule._cache_available_pools = available_pools

        cls.available_pools = DeadlineModule._cache_available_pools

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
                    default=cls.primary_pool),
            EnumDef("secondaryPool",
                    label="Secondary Pool",
                    items=pools,
                    default=cls.secondary_pool)
        ]
