import maya.cmds as cmds

from openpype.settings import get_current_project_settings
import openpype.hosts.maya.api.plugin
from openpype.hosts.maya.api import lib

from openpype.lib import get_creator_by_name
from openpype.pipeline import (
    legacy_io,
    legacy_create,
)


class YetiRigLoader(openpype.hosts.maya.api.plugin.ReferenceLoader):
    """This loader will load Yeti rig."""

    families = ["yetiRig"]
    representations = ["ma"]

    label = "Load Yeti Rig"
    order = -9
    icon = "code-fork"
    color = "orange"

    yeti_cache_creator_name = "CreateYetiCache"

    def process_reference(
        self, context, name=None, namespace=None, options=None
    ):
        group_name = options['group_name']
        with lib.maintained_selection():
            file_url = self.prepare_root_value(
                self.fname, context["project"]["name"]
            )
            nodes = cmds.file(
                file_url,
                namespace=namespace,
                reference=True,
                returnNewNodes=True,
                groupReference=True,
                groupName=group_name
            )

        settings = get_current_project_settings()
        colors = settings["maya"]["load"]["colors"]
        c = colors.get("yetiRig")
        if c is not None:
            cmds.setAttr(group_name + ".useOutlinerColor", 1)
            cmds.setAttr(
                group_name + ".outlinerColor",
                (float(c[0]) / 255), (float(c[1]) / 255), (float(c[2]) / 255)
            )
        self[:] = nodes

        # Automatically create in instance to allow publishing the loaded
        # yeti rig into a yeti cache
        self._create_yeti_cache_instance(nodes, subset=namespace)

        return nodes

    def _create_yeti_cache_instance(self, nodes, subset):

        from maya import cmds

        # Find the roots amongst the loaded nodes
        yeti_nodes = cmds.ls(nodes, type="pgYetiMaya", long=True)
        assert yeti_nodes, "No pgYetiMaya nodes in rig, this is a bug."

        self.log.info("Creating subset: {}".format(subset))

        # Create the animation instance
        creator_plugin = get_creator_by_name(self.yeti_cache_creator_name)
        with lib.maintained_selection():
            cmds.select(yeti_nodes, noExpand=True)
            legacy_create(
                creator_plugin,
                name=subset,
                asset=legacy_io.Session["AVALON_ASSET"],
                options={"useSelection": True}
            )
