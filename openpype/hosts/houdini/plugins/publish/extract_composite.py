import os
import pyblish.api

from openpype.pipeline import publish
from openpype.hosts.houdini.api.lib import render_rop


class ExtractComposite(publish.Extractor):

    order = pyblish.api.ExtractorOrder
    label = "Extract Composite (Image Sequence)"
    hosts = ["houdini"]
    families = ["imagesequence"]

    def process(self, instance):

        ropnode = instance[0]

        # Get the filename from the copoutput parameter
        # `.evalParm(parameter)` will make sure all tokens are resolved
        output = ropnode.evalParm("copoutput")
        staging_dir = os.path.dirname(output)
        instance.data["stagingDir"] = staging_dir
        file_name = os.path.basename(output)

        self.log.info("Writing comp '%s' to '%s'" % (file_name, staging_dir))

        render_rop(ropnode)

        output = instance.data["frames"]
        ext = os.path.splitext(output[0])[1].lstrip(".")

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            "name": ext,
            "ext": ext,
            "files": output if len(output) > 1 else output[0],
            "stagingDir": staging_dir,
            "frameStart": instance.data["frameStart"],
            "frameEnd": instance.data["frameEnd"],
        }

        instance.data["representations"].append(representation)
