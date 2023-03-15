import os

import pyblish.api

from openpype.pipeline import publish
from openpype.hosts.houdini.api.lib import render_rop

import hou


class ExtractBGEO(publish.Extractor):

    order = pyblish.api.ExtractorOrder
    label = "Extract BGEO"
    hosts = ["houdini"]
    families = ["bgeo"]

    def process(self, instance):

        ropnode = hou.node(instance.data["instance_node"])

        # Get the filename from the filename parameter
        output = ropnode.evalParm("sopoutput")
        staging_dir = os.path.dirname(output)
        instance.data["stagingDir"] = staging_dir

        file_name = os.path.basename(output)

        # We run the render
        self.log.info("Writing bgeo files '{}' to '{}'.".format(
            file_name, staging_dir))

        # write files
        render_rop(ropnode)

        output = instance.data["frames"]

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            "name": "bgeo",
            "ext": instance.data["bgeo_type"],
            "files": output,
            "stagingDir": staging_dir,
            "frameStart": instance.data["frameStart"],
            "frameEnd": instance.data["frameEnd"]
        }
        instance.data["representations"].append(representation)
