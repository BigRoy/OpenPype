from openpype.hosts.maya.api import (
    lib,
    plugin
)
from openpype.lib import NumberDef, BoolDef


class CreateGltf(plugin.MayaCreator):
    """Create glTF files using BabylonJS"""

    identifier = "io.openpype.creators.maya.gltf_babylonjs"
    label = "GLTF (BabylonJS)"
    family = "gltf"
    icon = "cubes"
    description = "Create glTF files using BabylonJS"

    def get_instance_attr_defs(self):
        # TODO: Support animation clips

        defs = lib.collect_animation_defs()
        defs.extend([
            NumberDef("scaleFactor",
                      label="Scale Factor",
                      default=1.0,
                      decimals=3),
            BoolDef("writeTextures",
                    label="Write Textures",
                    default=False),
            BoolDef("exportHiddenObjects",
                    label="Export Hidden Objects",
                    default=False),
            BoolDef("exportMaterials",
                    label="Export Materials",
                    default=True),
            BoolDef("exportTangents",
                    label="Export Tangents",
                    default=True),
            BoolDef("exportSkins",
                    label="Export Skins",
                    default=True),
            BoolDef("exportMorphTangents",
                    label="Export Morph Tangents",
                    default=True),
            BoolDef("exportMorphNormals",
                    label="Export Morph Normals",
                    default=True),
            BoolDef("exportAnimations",
                    label="Export Animations",
                    default=True),
            BoolDef("exportAnimationsOnly",
                    label="Export Animations Only",
                    default=False),
            BoolDef("exportTextures",
                    label="Export Textures",
                    default=True),
            BoolDef("bakeAnimationFrames",
                    label="Bake Animation Frames",
                    default=False),
            BoolDef("optimizeAnimations",
                    label="Optimize Animations",
                    default=True),
            BoolDef("optimizeVertices",
                    label="Optimize Vertices",
                    default=True),
            BoolDef("dracoCompression",
                    label="Draco Compression",
                    default=False)
        ])

        return defs
