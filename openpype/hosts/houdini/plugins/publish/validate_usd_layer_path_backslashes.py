# -*- coding: utf-8 -*-
import pyblish.api

import openpype.hosts.houdini.api.usd as hou_usdlib
from openpype.pipeline import (
    PublishValidationError,
    publish
)

import hou


class ValidateUSDLayerPathBackslashes(pyblish.api.InstancePlugin,
                                      publish.OptionalPyblishPluginMixin):
    """Validate USD loaded paths have no backslashes.

    This is a crucial validation for HUSK USD rendering as Houdini's
    USD Render ROP will fail to write out a .usd file for rendering that
    correctly preserves the backslashes, e.g. it will incorrectly convert a
    '\t' to a TAB character disallowing HUSK to find those specific files.

    This validation is redundant for usdModel since that flattens the model
    before write. As such it will never have any used layers with a path.

    """

    order = pyblish.api.ValidatorOrder
    families = ["usd", "usdrender"]
    hosts = ["houdini"]
    label = "USD Layer path backslashes"
    optional = True
    active = False

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        if not instance.data.get("instance_node"):
            # We don't actually want to skip instances 'silently' but we can't
            # show the optional attribute definition checkbox for an instance's
            # additional family expect for its primary family. As such, when
            # targeting this to `usdrop` which primarily is `usd` family it
            # won't show the attribute definition for instance with families
            # `["usd", "usdrop"]`. So instead we target `usd` and ignore any
            # USD instance that does not hav
            return

        rop = hou.node(instance.data.get("instance_node"))
        lop_path = hou_usdlib.get_usd_rop_loppath(rop)
        stage = lop_path.stage(apply_viewport_overrides=False)

        invalid = []
        for layer in stage.GetUsedLayers():
            references = layer.externalReferences

            for ref in references:

                # Ignore anonymous layers
                if ref.startswith("anon:"):
                    continue

                # If any backslashes in the path consider it invalid
                if "\\" in ref:
                    self.log.error("Found invalid path: %s" % ref)
                    invalid.append(layer)

        if invalid:
            raise PublishValidationError((
                "Loaded layers have backslashes. "
                "This is invalid for HUSK USD rendering."),
                title=self.label)
