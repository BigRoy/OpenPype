from openpype.hosts.fusion.api.plugin import GenericCreateSaver

from openpype.lib import (
    EnumDef,
    UILabelDef,
    NumberDef,
)
from openpype.hosts.fusion.api.lib import get_current_comp


class CreateSaver(GenericCreateSaver):
    """Fusion Saver to generate image sequence of 'render' product type.

     Original Saver creator targeted for 'render' product type. It uses
     original not to descriptive name because of values in Settings.
    """
    identifier = "io.openpype.creators.fusion.saver"
    label = "Render (saver)"
    name = "render"
    family = "render"
    description = "Fusion Saver to generate image sequence"

    default_frame_range_option = "asset_db"

    def get_detail_description(self):
        return """Fusion Saver to generate image sequence.

        This creator is expected for publishing of image sequences for 'render'
        product type. (But can publish even single frame 'render'.)

        Select what should be source of render range:
        - "Current asset context" - values set on Asset in DB (Ftrack)
        - "From render in/out" - from node itself
        - "From composition timeline" - from timeline

        Supports local and farm rendering.

        Supports selection from predefined set of output file extensions:
        - exr
        - tga
        - png
        - tif
        - jpg
        """

    def get_pre_create_attr_defs(self):
        """Settings for create page"""

        # Define custom frame range defaults based on current comp
        # timeline settings (if a comp is currently open)
        comp = get_current_comp()
        if comp is not None:
            attrs = comp.GetAttrs()
            frame_defaults = {
                "frameStart": int(attrs["COMPN_GlobalStart"]),
                "frameEnd": int(attrs["COMPN_GlobalEnd"]),
                "handleStart": int(
                    attrs["COMPN_RenderStart"] - attrs["COMPN_GlobalStart"]
                ),
                "handleEnd": int(
                    attrs["COMPN_GlobalEnd"] - attrs["COMPN_RenderEnd"]
                ),
            }
        else:
            frame_defaults = {
                "frameStart": 1001,
                "frameEnd": 1100,
                "handleStart": 0,
                "handleEnd": 0
            }

        attr_defs = [
            self._get_render_target_enum(),
            self._get_reviewable_bool(),
            self._get_frame_range_enum(),
            self._get_image_format_enum(),
            UILabelDef(
                label="<br><b>Custom Frame Range</b>"
            ),
            UILabelDef(
                label="<i>only used with 'Custom frame range' source</i>"
            ),
            NumberDef(
                "custom_frameStart",
                label="Frame Start",
                default=frame_defaults["frameStart"],
                minimum=0,
                decimals=0
            ),
            NumberDef(
                "custom_frameEnd",
                label="Frame End",
                default=frame_defaults["frameEnd"],
                minimum=0,
                decimals=0
            ),
            NumberDef(
                "custom_handleStart",
                label="Handle Start",
                default=frame_defaults["handleStart"],
                minimum=0,
                decimals=0
            ),
            NumberDef(
                "custom_handleEnd",
                label="Handle End",
                default=frame_defaults["handleEnd"],
                minimum=0,
                decimals=0
            )
        ]
        return attr_defs

    def _get_frame_range_enum(self):
        frame_range_options = {
            "asset_db": "Current asset context",
            "render_range": "From render in/out",
            "comp_range": "From composition timeline",
            "custom_range": "Custom frame range",
        }

        return EnumDef(
            "frame_range_source",
            items=frame_range_options,
            label="Frame range source",
            default=self.default_frame_range_option
        )
