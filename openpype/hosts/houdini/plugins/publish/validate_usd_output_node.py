# -*- coding: utf-8 -*-
import pyblish.api
from openpype.pipeline import PublishValidationError
from openpype.hosts.houdini.api.action import SelectROPAction


class ValidateUSDOutputNode(pyblish.api.InstancePlugin):
    """Validate the instance USD LOPs Output Node.

    This will ensure:
        - The LOP Path is set.
        - The LOP Path refers to an existing object.
        - The LOP Path node is a LOP node.

    """

    # Validate early so that this error reports higher than others to the user
    # so that if another invalidation is due to the output node being invalid
    # the user will likely first focus on this first issue
    order = pyblish.api.ValidatorOrder - 0.4
    families = ["usdrop"]
    hosts = ["houdini"]
    label = "Validate Output Node (USD)"
    actions = [SelectROPAction]

    def process(self, instance):

        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                ("Output node(s) `{}` are incorrect. "
                 "See plug-in log for details.").format(invalid),
                title=self.label
            )

    @classmethod
    def get_invalid(cls, instance):

        import hou

        output_node = instance.data.get("output_node")

        if output_node is None:
            node = hou.node(instance.data.get("instance_node"))
            cls.log.error(
                "USD node '%s' LOP path does not exist. "
                "Ensure a valid LOP path is set." % node.path()
            )

            return [node.path()]

        # Output node must be a Sop node.
        if not isinstance(output_node, hou.LopNode):
            cls.log.error(
                "Output node %s is not a LOP node. "
                "LOP Path must point to a LOP node, "
                "instead found category type: %s"
                % (output_node.path(), output_node.type().category().name())
            )
            return [output_node.path()]
