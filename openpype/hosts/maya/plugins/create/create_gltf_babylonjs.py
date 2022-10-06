from openpype.hosts.maya.api import (
    lib,
    plugin
)


class CreateGltf(plugin.Creator):
    """Create glTF files using BabylonJS"""

    name = "gltf"
    label = "GLTF"
    family = "gltf"
    icon = "cubes"

    def __init__(self, *args, **kwargs):
        super(CreateGltf, self).__init__(*args, **kwargs)

        # get basic animation data : start / end / handles / steps
        for key, value in lib.collect_animation_data().items():
            self.data[key] = value

        # Write vertex colors with the geometry.
        self.data["scaleFactor"] = 1.0

        self.data["writeTextures"] = False
        self.data["exportHiddenObjects"] = False
        self.data["exportMaterials"] = True
        self.data["exportTangents"] = True
        self.data["exportSkins"] = True
        self.data["exportMorphTangents"] = True
        self.data["exportMorphNormals"] = True
        self.data["exportAnimations"] = True
        self.data["exportAnimationsOnly"] = False
        self.data["exportTextures"] = True
        self.data["bakeAnimationFrames"] = False
        self.data["optimizeAnimations"] = True
        self.data["optimizeVertices"] = True
        self.data["dracoCompression"] = False

        # TODO: Support animation clips
