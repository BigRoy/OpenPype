# -*- coding: utf-8 -*-
import pyblish.api

from openpype.pipeline import PublishValidationError
from openpype.hosts.houdini.api.action import SelectROPAction

import hou
import pxr


class ValidateUSDRenderSettings(pyblish.api.InstancePlugin):
    """Generic export settings validator for USD Render ROP."""

    order = pyblish.api.ValidatorOrder
    families = ["usdrender"]
    hosts = ["houdini"]
    label = "Validate USD Render ROP Settings"
    actions = [SelectROPAction]

    def process(self, instance):
        # TODO: Validate "Render All Frames With a Single Process"
        # TODO: Validate $F in USD export filepath if not 'Single Process'

        # Get configured settings for this instance
        submission_data = (
            instance.data
            .get("publish_attributes", {})
            .get("HoudiniSubmitDeadline", {})
        )
        render_chunk_size = submission_data.get("chunk", 1)
        export_chunk_size = submission_data.get("export_chunk", 1)
        usd_file_per_frame = "$F" in instance.data["ifdFile"]
        frame_start_handle = instance.data["frameStartHandle"]
        frame_end_handle = instance.data["frameEndHandle"]
        num_frames = frame_end_handle - frame_start_handle + 1
        rop_node = hou.node(instance.data["instance_node"])

        # Whether ROP node is set to render all Frames within a single process
        # When this is disabled then Husk will restart completely per frame
        # no matter the chunk size.
        all_frames_at_once = rop_node.evalParm("allframesatonce")

        invalid = False
        if usd_file_per_frame:
            # USD file per frame
            # If rendering multiple frames per task and USD file has $F then
            # log a warning that the optimization will be less efficient
            # since husk will still restart per frame.
            if render_chunk_size > 1:
                self.log.warning(
                    "Render chunk size is bigger than one but export file is "
                    "a USD file per frame. Husk does not allow rendering "
                    "separate USD files in one process. As such, Husk will "
                    "restart per frame even within the chunk to render the "
                    "correct file per frame."
                )
        else:
            # Single export USD file
            # Export chunk size must be higher than the amount of frames to
            # ensure the file is written in one go on one machine and thus
            # ends up containing all frames correctly
            if export_chunk_size < num_frames:
                self.log.error(
                    "Export chunk size '%s' is smaller than the amount of "
                    "frames '%s'. The export file is not a file per frame."
                    "Hence data will be lost because multiple frames will "
                    "write into the same file. Make sure to increase chunk "
                    "size to higher than the amount of frames to render: >%s",
                    export_chunk_size, num_frames, num_frames
                )
                invalid = True

            if all_frames_at_once and render_chunk_size > 1:
                self.log.debug(
                    "USD Render ROP is set to render all frames within a "
                    "single process with a chunk size of %s",
                    render_chunk_size
                )

        if invalid:
            raise PublishValidationError("Invalid, see logs.")


class ValidateUSDRenderArnoldSettings(pyblish.api.InstancePlugin):
    """Validate USD Render Product names are correctly set absolute paths."""

    order = pyblish.api.ValidatorOrder
    families = ["usdrender"]
    hosts = ["houdini"]
    label = "Validate USD Render Arnold Settings"
    actions = [SelectROPAction]

    def process(self, instance):

        rop_node = hou.node(instance.data["instance_node"])
        node = instance.data.get("output_node")

        # Check only for Arnold renderer
        renderer = rop_node.evalParm("renderer")
        if renderer != "HdArnoldRendererPlugin":
            self.log.debug("Skipping Arnold Settings validation because "
                           "renderer is set to: %s", renderer)
            return

        # Validate Arnold Product Type is enabled on the Arnold Render Settings
        # This is confirmed by the `includeAovs` attribute on the RenderProduct
        stage: pxr.Usd.Stage = node.stage()
        invalid = False
        for prim_path in instance.data.get("usdRenderProducts", []):
            prim = stage.GetPrimAtPath(prim_path)
            include_aovs = prim.GetAttribute("includeAovs")
            if not include_aovs.IsValid() or not include_aovs.Get(0):
                self.log.error(
                    "All Render Products must be set to 'Arnold Product "
                    "Type' on the Arnold Render Settings node to ensure "
                    "correct output of metadata and AOVs."
                )
                invalid = True
                break

        # Ensure 'Delegate Products' is enabled for Husk
        if not rop_node.evalParm("husk_delegateprod"):
            invalid = True
            self.log.error("USD Render ROP has `Husk > Rendering > Delegate "
                           "Products` disabled. Please enable to ensure "
                           "correct output files")

        # TODO: Detect bug of invalid Cryptomatte state?
        # Detect if any Render Products were set that do not actually exist
        # (e.g. invalid rendervar targets for a renderproduct) because that
        # is what originated the Cryptomatte enable->disable bug.

        if invalid:
            raise PublishValidationError(
                "Invalid Render Settings for Arnold render."
            )
