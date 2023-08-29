import pyblish.api

from openpype.pipeline import (
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from openpype.modules.deadline.deadline_module import DeadlineModule


class ValidateDeadlinePools(OptionalPyblishPluginMixin,
                            pyblish.api.InstancePlugin):
    """Validate primaryPool and secondaryPool on instance.

    Values are on instance based on value insertion when Creating instance or
    by Settings in CollectDeadlinePools.
    """

    label = "Validate Deadline Pools"
    order = pyblish.api.ValidatorOrder
    families = ["rendering",
                "render.farm",
                "render.frames_farm",
                "renderFarm",
                "renderlayer",
                "maxrender"]
    optional = True

    pools_for_deadline_url = {}

    def process(self, instance):
        if not instance.data.get("farm"):
            self.log.debug("Skipping local instance.")
            return

        # get default deadline webservice url from deadline module
        deadline_url = instance.context.data["defaultDeadline"]
        pools = self.get_pools(deadline_url)

        primary_pool = instance.data.get("primaryPool")
        if primary_pool and primary_pool not in pools:
            msg = "Configured primary '{}' not present on Deadline".format(
                instance.data["primaryPool"])
            self.raise_error(msg, pools)

        secondary_pool = instance.data.get("secondaryPool")
        if secondary_pool and secondary_pool not in pools:
            msg = "Configured secondary '{}' not present on Deadline".format(
                instance.data["secondaryPool"])
            self.raise_error(msg, pools)

    def raise_error(self, msg, pools):
        formatting_data = {
            "pools_str": ",".join(sorted(pools)),
            "invalid_value_str": msg
        }
        raise PublishXmlValidationError(self, msg,
                                        formatting_data=formatting_data)

    def get_pools(self, deadline_url):
        if deadline_url not in self.pools_for_deadline_url:
            self.log.debug(
                "Querying pools for Deadline URL: {}".format(deadline_url)
            )
            pools = DeadlineModule.get_deadline_pools(deadline_url,
                                                      log=self.log)
            self.log.debug("Found Deadline pools: {}".format(pools))
            self.pools_for_deadline_url[deadline_url] = set(pools)

        return self.pools_for_deadline_url[deadline_url]
