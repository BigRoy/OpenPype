# -*- coding: utf-8 -*-
"""Creator plugin for creating USD renders."""
from openpype.hosts.houdini.api import plugin
from openpype.pipeline import CreatedInstance
from openpype.lib import BoolDef


class CreateUSDRender(plugin.HoudiniCreator):
    """USD Render ROP in /stage"""
    identifier = "io.openpype.creators.houdini.usdrender"
    label = "USD Render"
    family = "usdrender"
    icon = "magic"

    split_render = True

    def create(self, subset_name, instance_data, pre_create_data):
        import hou  # noqa

        # TODO: Support creation in /stage if wanted by user
        # pre_create_data["parent"] = "/stage"

        # Remove the active, we are checking the bypass flag of the nodes
        instance_data.pop("active", None)
        instance_data.update({"node_type": "usdrender"})

        instance = super(CreateUSDRender, self).create(
            subset_name,
            instance_data,
            pre_create_data)  # type: CreatedInstance

        instance_node = hou.node(instance.get("instance_node"))

        parms = {
            # Render frame range
            "trange": 1
        }
        if self.selected_nodes:
            parms["loppath"] = self.selected_nodes[0].path()

        if pre_create_data.get("split_render", self.split_render):
            # Do not trigger the husk render, only trigger the USD export
            parms["runcommand"] = False
            # By default the render ROP writes out the render file to a
            # temporary directory. But if we want to render the USD file on
            # the farm we instead want it in the project available
            # to all machines. So we ensure all USD files are written to a
            # folder to our choice. The
            # `__render__.usd` (default name, defined by `lopoutput` parm)
            # in that folder will then be the file to render.
            parms["savetodirectory_directory"] = "$HIP/render/usd/$HIPNAME/$OS"
            parms["lopoutput"] = "__render__.usd"

        instance_node.setParms(parms)

        # Lock some Avalon attributes
        to_lock = ["family", "id"]
        self.lock_parameters(instance_node, to_lock)

    def get_pre_create_attr_defs(self):
        return [
            BoolDef("split_render",
                    label="Split export and render jobs",
                    default=self.split_render),
        ]
