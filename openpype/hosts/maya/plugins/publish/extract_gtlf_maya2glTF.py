from maya import cmds  # noqa
import maya.mel as mel  # noqa
import pyblish.api

from openpype.pipeline import publish
from openpype.hosts.maya.api.lib import maintained_selection

from maya import (
    cmds,
    mel
)


class ExtractGLTFmaya2glTF(publish.Extractor):
    """Extract GLTF from Maya.

    Extract GLTF from maya using iimachines/Maya2glTF
        Github: https://github.com/iimachines/Maya2glTF

    """
    order = pyblish.api.ExtractorOrder
    label = "Extract GLTF"
    families = ["gltf"]

    def process(self, instance):

        cmds.loadPlugin("maya2glTF", quiet=True)

        filename = instance.name
        staging_dir = self.staging_dir(instance)

        cameras = cmds.ls(instance[:], type="camera", long=True)

        options = {
            "copyright": "Colorbleed",
            "cameras": cameras,
            "outputFolder": staging_dir,
            "sceneName": filename,
            "selectedNodesOnly": True,
            "visibleNodesOnly": True,
            "defaultMaterial": True,
            "skipStandardMaterials": True
        }

        # Get customizable settings from instance
        for key in [
            "scaleFactor",
            "binary",
            "niceBufferURIs",
            #"hashBufferURI",
            "externalTextures",
            "initialValuesTime",
            "detectStepAnimations",
            "meshPrimitiveAttributes",
            "blendPrimitiveAttributes",
            "force32bitIndices",
            "mikkelsenTangentSpace",
            "excludeUnusedTexcoord",
        ]:
            options[key] = instance.data[key]

        # Export
        with maintained_selection():
            cmds.select(instance[:], r=1, noExpand=True)
            cmds.maya2glTF(**options)

        representations = instance.data.setdefault("representations", [])
        representations.append({
            'name': 'gltf',
            'ext': 'gltf',
            'files': filename,
            "stagingDir": staging_dir,
        })

        import subprocess
        subprocess.Popen(r'explorer "{}"'.format(staging_dir))
        raise RuntimeError
