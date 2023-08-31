from openpype.hosts.maya.api import (
    plugin
)
from openpype.lib import (
    BoolDef,
    EnumDef
)
from maya.app.renderSetup.model import renderSetup


def get_legacy_layer_name(layer):
    from maya import cmds

    if hasattr(layer, "legacyRenderLayer"):
        connections = cmds.listConnections(
            "{}.legacyRenderLayer".format(layer.name()),
            type="renderLayer",
            exactType=True,
            source=True,
            destination=False,
            plugs=False
        ) or []
        return next(iter(connections), None)
    else:
        # e.g. for DefaultRenderLayer
        return layer.name()


class CreateLook(plugin.MayaCreator):
    """Shader connections defining shape look"""

    identifier = "io.openpype.creators.maya.look"
    label = "Look"
    family = "look"
    icon = "paint-brush"

    make_tx = True
    rs_tex = False

    def get_instance_attr_defs(self):

        # Get render setup layers and their legacy names since we use the
        # legacy names to toggle to those layers in the codebase.
        rs = renderSetup.instance()
        renderlayers = [rs.getDefaultRenderLayer()]
        renderlayers.extend(rs.getRenderLayers())
        renderlayers = {
            get_legacy_layer_name(layer): layer.name()
            for layer in renderlayers
        }
        current_renderlayer = get_legacy_layer_name(rs.getVisibleRenderLayer())

        return [
            EnumDef("renderLayer",
                    default=current_renderlayer,
                    items=renderlayers,
                    label="Renderlayer",
                    tooltip="Renderlayer to extract the look from"),
            BoolDef("maketx",
                    label="Convert textures to .tx",
                    tooltip="Whether to generate .tx files for your textures",
                    default=self.make_tx),
            BoolDef("rstex",
                    label="Convert textures to .rstex",
                    tooltip="Whether to generate Redshift .rstex files for "
                            "your textures",
                    default=self.rs_tex),
            # Colorbleed edit: Disallow any changes to 'force copy'
            BoolDef("forceCopy",
                    label="Force Copy",
                    hidden=True,
                    tooltip="Enable users to force a copy instead of hardlink."
                            "\nNote: On Windows copy is always forced due to "
                            "bugs in windows' implementation of hardlinks.",
                    default=True)
        ]

    def get_pre_create_attr_defs(self):
        # Show same attributes on create but include use selection
        defs = super(CreateLook, self).get_pre_create_attr_defs()
        defs.extend(self.get_instance_attr_defs())
        return defs
