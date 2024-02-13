# -*- coding: utf-8 -*-
import inspect

import pyblish.api

from openpype.hosts.houdini.api.action import SelectROPAction
from openpype.pipeline import PublishValidationError

import hou


class ValidateUSDRopDefaultPrim(pyblish.api.InstancePlugin):
    """Validate the default prim exists if
     """

    order = pyblish.api.ValidatorOrder
    families = ["usdrop"]
    hosts = ["houdini"]
    label = "Validate USD ROP Default Prim"
    actions = [SelectROPAction]

    def process(self, instance):

        rop_node = hou.node(instance.data["instance_node"])

        default_prim = rop_node.evalParm("defaultprim")

        if not default_prim:
            self.log.debug(
                "No default prim specified on ROP node: %s", rop_node.path()
            )
            return

        lop_node: hou.LopNode = instance.data.get("output_node")
        if not lop_node:
            return

        above_break_layers = set(layer for layer in lop_node.layersAboveLayerBreak())
        stage = lop_node.stage()
        layers = [
            layer for layer
            in stage.GetLayerStack(includeSessionLayers=False)
            if layer.identifier not in above_break_layers
        ]
        if not layers:
            self.log.error("No USD layers found. This is likely a bug.")
            return

        # TODO: This only would detect any local opinions on that prim and thus
        #   would fail to detect if a sublayer added on the stage root layer
        #   being exported would actually be generating the prim path. We
        #   should maybe consider that if this fails that we still check
        #   whether a sublayer doesn't create the default prim path.
        for layer in layers:
            if layer.GetPrimAtPath(default_prim):
                break
        else:
            # No prim found at the given path on any of the generated layers
            raise PublishValidationError(
                "Default prim specified by USD ROP does not exist in "
                f"stage: '{default_prim}'",
                title="Default Prim",
                description=self.get_description()
            )

    def get_description(self):
        return inspect.cleandoc(
            """### Default Prim not found

            The USD render ROP is currently configured to write the output
            USD file with a default prim. However, the default prim is not
            found in the USD stage.

            Make sure to double check the Default Prim setting on the USD
            Render ROP for typos or make sure the hierarchy and opinions you
            are creating exist in the default prim path.

            """
        )
