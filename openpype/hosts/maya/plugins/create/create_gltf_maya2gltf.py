from openpype.hosts.maya.api import (
    lib,
    plugin
)


class CreateGltf(plugin.Creator):
    """Create glTF files using Maya2glTF"""

    name = "gltf"
    label = "GLTF"
    family = "gltf"
    icon = "cubes"

    def __init__(self, *args, **kwargs):
        super(CreateGltf, self).__init__(*args, **kwargs)

        # create an ordered dict with the existing data first
        self.data["animation"] = False

        # get basic animation data : start / end / handles / steps
        for key, value in lib.collect_animation_data().items():
            self.data[key] = value

        # Write vertex colors with the geometry.
        self.data["scaleFactor"] = 1.0
        self.data["binary"] = False
        self.data["niceBufferURIs"] = False
        self.data["hashBufferURI"] = False
        self.data["externalTextures"] = False  # only valid with `binary`
        self.data["initialValuesTime"] = self.data["frameStart"]
        self.data["detectStepAnimations"] = 2
        self.data["meshPrimitiveAttributes"] = "POSITION|NORMAL|TANGENT|TEXCOORD|COLOR|JOINTS|WEIGHTS"
        self.data["blendPrimitiveAttributes"] = "POSITION|NORMAL|TANGENT"
        self.data["force32bitIndices"] = False
        self.data["mikkelsenTangentSpace"] = False
        self.data["skipStandardMaterials"] = True
        self.data["excludeUnusedTexcoord"] = False

        # TODO: Support animation clips
