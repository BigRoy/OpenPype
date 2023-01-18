from maya import cmds

import pyblish.api

from openpype.hosts.maya.api import lib


SETTINGS = {
    # Preview
    "displayOutput",
    "colorR", "colorG", "colorB",
    "viewportDensity",
    "viewportWidth",
    "viewportLength",
    # Render attributes
    "renderDensity",
    "renderWidth",
    "renderLength",
    "increaseRenderBounds",
    "imageSearchPath",
    # Pipeline specific
    "cbId"
}


def get_yeti_user_variables(node):
    """Collect Yeti graph user variables (attributes + values)

    Output data example:
    {
        "yetiVariableF_bestpipelineintheworld": 666.0,
        "yetiVariableF_foobar": 0.0,
        "yetiVariableF_answertolife": 42.0,
        "yetiVariableV_myvector": [-0.5, 5.11, 0.0]
    }

    Arguments:
        node (str): Maya Yeti Graph node name (pgYetiMaya)

    Returns:
        dict: Attribute name: value

    """

    variables = dict()

    for attr in cmds.listAttr(node, string="yetiVariable*", userDefined=True) or []:
        if attr.startswith("yetiVariableF_"):
            # Float attributes
            plug = "{}.{}".format(node, attr)
            variables[attr] = cmds.getAttr(plug)

        elif attr.startswith("yetiVariableV_"):
            # Vector attributes
            plug = "{}.{}".format(node, attr)
            if cmds.attributeQuery(attr, node=node, listParent=True):
                # Ignore the individual channels of the attribute,
                # we will only collect the top level vector variable
                continue
            variables[attr] = cmds.getAttr(plug)[0]

    return variables


class CollectYetiCache(pyblish.api.InstancePlugin):
    """Collect all information of the Yeti caches

    The information contains the following attributes per Yeti node

    - "renderDensity"
    - "renderWidth"
    - "renderLength"
    - "increaseRenderBounds"
    - "imageSearchPath"

    Other information is the name of the transform and it's Colorbleed ID
    """

    order = pyblish.api.CollectorOrder + 0.45
    label = "Collect Yeti Cache"
    families = ["yetiRig", "yeticache"]
    hosts = ["maya"]

    def process(self, instance):

        # Collect fur settings
        settings = {"nodes": []}

        # Get yeti nodes and their transforms
        yeti_shapes = cmds.ls(instance, type="pgYetiMaya")
        for shape in yeti_shapes:

            # Get specific node attributes
            attr_data = {}
            for attr in SETTINGS:
                current = cmds.getAttr("%s.%s" % (shape, attr))
                # change None to empty string as Maya doesn't support
                # NoneType in attributes
                if current is None:
                    current = ""
                attr_data[attr] = current

            # Get transform data
            parent = cmds.listRelatives(shape, parent=True)[0]
            transform_data = {"name": parent, "cbId": lib.get_id(parent)}

            shape_data = {
                "transform": transform_data,
                "name": shape,
                "cbId": lib.get_id(shape),
                "attrs": attr_data,
            }

            # Optional user variables
            user_variables = get_yeti_user_variables(shape)
            if user_variables:
                shape_data["user_variables"] = user_variables

            settings["nodes"].append(shape_data)

        instance.data["fursettings"] = settings
