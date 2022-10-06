import os
import uuid
import contextlib
from collections import OrderedDict

import pyblish.api

from openpype.pipeline import publish
from openpype.hosts.maya.api.lib import (
    maintained_selection,
    pairwise
)

from maya import (
    cmds,
    mel
)


PARAMETERS = OrderedDict((
    ("outputPath", None),
    ("outputFormat", None),
    ("textureFolder", ""),
    ("scaleFactor", 1.0),
    ("writeTextures", False),
    ("overwriteTextures", True),
    ("exportHiddenObjects", False),
    ("exportMaterials", True),
    ("exportOnlySelected", True),
    ("bakeAnimationFrames", False),
    ("optimizeAnimations", True),
    ("optimizeVertices", True),
    ("animgroupExportNonAnimated", False),
    ("generateManifest", False),
    ("autoSaveSceneFile", False),
    ("exportTangents", True),
    ("exportSkins", True),
    ("exportMorphTangents", True),
    ("exportMorphNormals", True),
    ("txtQuality", 100),    # Texture quality percentage
    ("mergeAO", True),
    ("dracoCompression", False),
    ("enableKHRLightsPunctual", False),
    ("enableKHRTextureTransform", False),
    ("enableKHRMaterialsUnlit", False),
    ("pbrFull", False),
    ("pbrNoLight", True),
    ("createDefaultSkybox", False),
    ("pbrEnvironment", ""),
    ("exportAnimations", True),
    ("exportAnimationsOnly", False),
    ("exportTextures", True)
))


def _mel_cmd_value_str(value):
    safe_str = str(value).replace("\\", "/").replace('"', '\"')
    return f'"{safe_str}"'


@contextlib.contextmanager
def fileinfo(data):
    """Set Maya scene file info during context"""
    original = dict(pairwise(cmds.fileInfo(query=True)))
    try:
        for key, value in data.items():
            if value is None:
                cmds.fileInfo(remove=key)
            else:
                cmds.fileInfo(key, value)
        yield
    finally:
        after = dict(pairwise(cmds.fileInfo(query=True)))
        for key, value in after.items():
            if key not in original:
                cmds.fileInfo(remove=key)
            elif original[key] != value:
                cmds.fileInfo(key, original[key])


@contextlib.contextmanager
def animation_settings(animations):
    """Set BabylonJS exporter scene file info animation data during context"""
    if animations is None:
        # Passthrough, don't apply any overrides and use the stored settings
        yield
        return

    data = {}
    for animation in animations:
        assert len(animation) == 3, (
            "Animation must be a three-tuple: name, start, end"
        )
        anim_uuid = str(uuid.uuid4())
        data[anim_uuid] = ";".join(str(value) for value in animation) + ";"
    if animations:
        # Set the entries
        data["babylonjs_AnimationList"] = ";".join(data.keys())
    else:
        # Delete any existing entries
        data["babylonjs_AnimationList"] = None

    with fileinfo(data):
        yield


def export_babylonjs(outputPath,
                     outputFormat="gltf",
                     animations=None,
                     **kwargs):

    # Use default ordered dict of parameters
    parameters = PARAMETERS.copy()
    parameters["outputPath"] = outputPath
    parameters["outputFormat"] = outputFormat

    # Handle kwargs
    invalid_kwargs = []
    for key, value in kwargs.items():
        if key in parameters:
            parameters[key] = value
        else:
            invalid_kwargs.append(key)
    if invalid_kwargs:
        raise ValueError("Invalid parameter names provided for BabylonJS "
                         "export: {}".format(", ".join(invalid_kwargs)))

    # Validate parameters
    invalid_parameters = []
    for key, value in parameters.items():
        if value is None:
            invalid_parameters.append(f"{key} = {value}")
    if invalid_parameters:
        raise ValueError(
            "Invalid parameter values provided for BabylonJS export: "
            "{}".format(", ".join(invalid_parameters))
        )

    if animations:
        parameters["exportAnimations"] = True

    # Construct and run mel command
    export_parameters_str = ", ".join(
        _mel_cmd_value_str(value) for value in parameters.values()
    )

    cmd = f"ScriptToBabylon -exportParameters {{{export_parameters_str}}};"
    with animation_settings(animations):
        mel.eval(cmd)


class ExtractGLTFBabylonJS(publish.Extractor):
    """Extract GLTF from Maya using BabylonJS Exporter.

        Source: https://github.com/BabylonJS/Exporters
    """
    order = pyblish.api.ExtractorOrder
    label = "Extract GLTF"
    families = ["gltf"]

    def process(self, instance):

        cmds.loadPlugin("Maya2Babylon", quiet=True)

        filename = instance.name + ".gltf"
        staging_dir = self.staging_dir(instance)
        filepath = os.path.join(staging_dir, filename)

        animations = instance.data.get("animations", [])
        # [("intro", 1, 100), ("outro", 150, 250)]
        if not animations:
            self.log.debug("No animations provided, "
                           "falling back to scene animations if animation "
                           "is enabled.")
            animations = None

        # Take overrides from the instance
        override_parameters = {}
        for key, default in PARAMETERS.items():
            if key in instance.data:
                value = instance.data[key]
                if value != default:
                    self.log.debug(f"Override {key} = {value}")
                    override_parameters[key] = value

        # Export
        self.log.info(f"Extracting to: {filepath}")
        with maintained_selection():
            cmds.select(instance[:], r=1, noExpand=True)
            export_babylonjs(outputPath=filepath,
                             animations=animations,
                             **override_parameters)

        # The GLTF format will introduce additional file outputs like .bin
        # binary data and potentially textures that are referenced by name
        # from the main .gltf file - we'll want to transfer those explicitly
        # into the published folder to ensure those links remain correct.
        transfers = instance.data.setdefault("transfers", [])
        publish_dir = instance.data["publishDir"]
        for fname in os.listdir(staging_dir):
            if fname == filename:
                # Exclude the main file
                continue
            source = os.path.join(staging_dir, fname)
            destination = os.path.join(publish_dir, fname)
            self.log.debug(f"Adding resource: {fname}")
            transfers.append((source, destination))

        representations = instance.data.setdefault("representations", [])
        representations.append({
            'name': 'gltf',
            'ext': 'gltf',
            'files': filename,
            "stagingDir": staging_dir,
        })
