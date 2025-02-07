import os

import pyblish.api

from openpype.pipeline import publish
from openpype.hosts.houdini.api.lib import render_rop

import hou


class ExtractOpenGL(publish.Extractor):

    order = pyblish.api.ExtractorOrder - 0.01
    label = "Extract OpenGL"
    families = ["review"]
    hosts = ["houdini"]

    def process(self, instance):
        ropnode = hou.node(instance.data.get("instance_node"))

        output = ropnode.evalParm("picture")
        staging_dir = os.path.normpath(os.path.dirname(output))
        instance.data["stagingDir"] = staging_dir
        file_name = os.path.basename(output)

        self.log.info("Extracting '%s' to '%s'" % (file_name,
                                                   staging_dir))

        render_rop(ropnode)

        # Unfortunately user interrupting the extraction does not raise an
        # error and thus still continues to the integrator. To capture that
        # we make sure all files exist
        output = instance.data["frames"]
        missing = [fname for fname in output
                   if not os.path.exists(os.path.join(staging_dir, fname))]
        if missing:
            raise RuntimeError("Failed to complete review extraction. "
                               "Missing output files: {}".format(missing))

        tags = ["review"]
        if not instance.data.get("keepImages"):
            tags.append("delete")

        representation = {
            "name": instance.data["imageFormat"],
            "ext": instance.data["imageFormat"],
            "files": output if len(output) > 1 else output[0],
            "stagingDir": staging_dir,
            "frameStart": instance.data["frameStartHandle"],
            "frameEnd": instance.data["frameEndHandle"],
            "tags": tags,
            "preview": True,
            "camera_name": instance.data.get("review_camera")
        }

        if "representations" not in instance.data:
            instance.data["representations"] = []
        instance.data["representations"].append(representation)
