import hou
import pyblish.api


class CollectHoudiniReviewData(pyblish.api.InstancePlugin):
    """Collect Review Data."""

    label = "Collect Review Data"
    order = pyblish.api.CollectorOrder + 0.1
    hosts = ["houdini"]
    families = ["review"]

    def process(self, instance):

        # Set current houdini fps on the instance
        # Required for global Extract review plug-in
        instance.data["fps"] = hou.fps()
