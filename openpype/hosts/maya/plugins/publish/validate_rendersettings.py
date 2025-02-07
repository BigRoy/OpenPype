# -*- coding: utf-8 -*-
"""Maya validator for render settings."""
import re
from collections import OrderedDict

from maya import cmds, mel

import pyblish.api
from openpype.pipeline.publish import (
    RepairAction,
    ValidateContentsOrder,
    PublishValidationError,
)
from openpype.hosts.maya.api import lib
from openpype.hosts.maya.api.lib_rendersettings import RenderSettings
from openpype.hosts.maya.api.lib_renderproducts import (
    R_AOV_TOKEN,
    R_LAYER_TOKEN
)


def convert_to_int_or_float(string_value):
    # Order of types are important here since float can convert string
    # representation of integer.
    types = [int, float]
    for t in types:
        try:
            result = t(string_value)
        except ValueError:
            continue
        else:
            return result

    # Neither integer or float.
    return string_value


def get_redshift_image_format_labels():
    """Return nice labels for Redshift image formats."""
    var = "$g_redshiftImageFormatLabels"
    return mel.eval("{0}={0}".format(var))


class ValidateRenderSettings(pyblish.api.InstancePlugin):
    """Validates the global render settings

    * File Name Prefix must start with: `<Scene>`
        all other token are customizable but sane values for Arnold are:

        `<Scene>/<RenderLayer>/<RenderLayer>_<RenderPass>`

        <Camera> token is supported also, useful for multiple renderable
        cameras per render layer.

        For Redshift omit <RenderPass> token. Redshift will append it
        automatically if AOVs are enabled and if you user Multipart EXR
        it doesn't make much sense.

    * Frame Padding must be:
        * default: 4

    * Animation must be toggle on, in Render Settings - Common tab:
        * vray: Animation on standard of specific
        * arnold: Frame / Animation ext: Any choice without "(Single Frame)"
        * redshift: Animation toggled on

    NOTE:
        The repair function of this plugin does not repair the animation
        setting of the render settings due to multiple possibilities.

    """

    order = ValidateContentsOrder
    label = "Render Settings"
    hosts = ["maya"]
    families = ["renderlayer"]
    actions = [RepairAction]

    _required_globals = {
        "outFormatControl": 0,
        "animation": 1,
        "putFrameBeforeExt": 1,
        # 0: No period, 1: Period `.`, 2: Underscore `_`
        "periodInExt": 1,
        "extensionPadding": 4
    }

    redshift_AOV_prefix = "<BeautyPath>/<BeautyFile>{aov_separator}<RenderPass>"  # noqa: E501

    renderman_dir_prefix = "<scene>/<layer>"

    R_CAMERA_TOKEN = re.compile(r'%c|Camera>')
    R_SCENE_TOKEN = re.compile(r'%s|<scene>', re.IGNORECASE)

    DEFAULT_PADDING = 4
    VRAY_PREFIX = "<Scene>/<Layer>/<Layer>"
    DEFAULT_PREFIX = "<Scene>/<RenderLayer>/<RenderLayer>_<RenderPass>"

    def process(self, instance):

        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                title="Invalid Render Settings",
                message=("Invalid render settings found "
                         "for '{}'!".format(instance.name))
            )

    @classmethod
    def get_invalid(cls, instance):

        invalid = False

        renderer = instance.data['renderer']
        layer = instance.data['renderlayer']
        cameras = instance.data.get("cameras", [])

        render_settings = RenderSettings(
            project_settings=instance.context.data["project_settings"])

        # Get current image prefix and padding set in scene
        # Prefix attribute can return None when a value was never set
        prefix = lib.get_attr_in_layer(
            render_settings.get_image_prefix_attr(renderer), layer=layer) or ""
        padding = lib.get_attr_in_layer(
            render_settings.get_padding_attr(renderer), layer=layer)

        anim_override = lib.get_attr_in_layer("defaultRenderGlobals.animation",
                                              layer=layer)

        prefix = prefix.replace(
            "{aov_separator}", instance.data.get("aovSeparator", "_"))

        default_prefix = render_settings.get_default_image_prefix(
            renderer, format_aov_separator=False)
        aov_separator = render_settings.get_aov_separator()

        if not anim_override:
            invalid = True
            cls.log.error("Animation needs to be enabled. Use the same "
                          "frame for start and end to render single frame")

        if not re.search(R_LAYER_TOKEN, prefix):
            invalid = True
            cls.log.error("Wrong image prefix [ {} ] - "
                          "doesn't have: '<renderlayer>' or "
                          "'<layer>' token".format(prefix))

        if len(cameras) > 1 and not re.search(cls.R_CAMERA_TOKEN, prefix):
            invalid = True
            cls.log.error("Wrong image prefix [ {} ] - "
                          "doesn't have: '<Camera>' token".format(prefix))
            cls.log.error(
                "Note that it needs to have capital 'C' at the beginning")

        # renderer specific checks
        if renderer == "vray":
            vray_settings = cmds.ls(type="VRaySettingsNode")
            if not vray_settings:
                node = cmds.createNode("VRaySettingsNode")
            else:
                node = vray_settings[0]

            scene_sep = cmds.getAttr(
                "{}.fileNameRenderElementSeparator".format(node))
            if scene_sep != instance.data.get("aovSeparator", "_"):
                cls.log.error("AOV separator is not set correctly.")
                invalid = True

        if renderer == "redshift":
            redshift_AOV_prefix = cls.redshift_AOV_prefix.replace(
                "{aov_separator}", aov_separator
            )
            if re.search(R_AOV_TOKEN, prefix):
                invalid = True
                cls.log.error(("Do not use AOV token [ {} ] - "
                               "Redshift is using image prefixes per AOV so "
                               "it doesn't make much sense using it in global"
                               "image prefix").format(prefix))
            # get redshift AOVs
            rs_aovs = cmds.ls(type="RedshiftAOV", referencedNodes=False)
            for aov in rs_aovs:
                aov_prefix = cmds.getAttr("{}.filePrefix".format(aov))
                # check their image prefix
                if aov_prefix != redshift_AOV_prefix:
                    cls.log.error(("AOV ({}) image prefix is not set "
                                   "correctly {} != {}").format(
                        cmds.getAttr("{}.name".format(aov)),
                        aov_prefix,
                        redshift_AOV_prefix
                    ))
                    invalid = True

                # check aov file format
                aov_ext = cmds.getAttr("{}.fileFormat".format(aov))
                default_ext = cmds.getAttr("redshiftOptions.imageFormat")
                aov_type = cmds.getAttr("{}.aovType".format(aov))
                if aov_type == "Cryptomatte":
                    # redshift Cryptomatte AOV always uses "Cryptomatte (EXR)"
                    # so we ignore validating file format for it.
                    pass

                elif default_ext != aov_ext:
                    labels = get_redshift_image_format_labels()
                    cls.log.error(
                        "AOV file format {} does not match global file format "
                        "{}".format(labels[aov_ext], labels[default_ext])
                    )
                    invalid = True

        if renderer == "renderman":
            file_prefix = cmds.getAttr("rmanGlobals.imageFileFormat")
            dir_prefix = cmds.getAttr("rmanGlobals.imageOutputDir")

            if file_prefix.lower() != prefix.lower():
                invalid = True
                cls.log.error("Wrong image prefix [ {} ]".format(file_prefix))

            if dir_prefix.lower() != cls.renderman_dir_prefix.lower():
                invalid = True
                cls.log.error("Wrong directory prefix [ {} ]".format(
                    dir_prefix))

        if renderer == "arnold":
            multipart = cmds.getAttr("defaultArnoldDriver.mergeAOVs")
            multipart_default = render_settings.get(
                "arnold_renderer/multilayer_exr", True)
            if multipart != multipart_default:
                cls.log.warning("Warning: Merge AOVs differs from project "
                                "recommended: {}".format(multipart_default))

            prefix_has_aov_token = re.search(R_AOV_TOKEN, prefix)
            if multipart:
                if prefix_has_aov_token:
                    invalid = True
                    cls.log.error("Wrong image prefix [ {} ] - "
                                  "You can't use '<renderpass>' token "
                                  "with merge AOVs turned on".format(prefix))
            elif not prefix_has_aov_token:
                invalid = True
                cls.log.error("Wrong image prefix [ {} ] - "
                              "You must have: '<renderpass>' token "
                              "with merge AOVs turned off".format(prefix))

        default_prefix = default_prefix.replace("{aov_separator}",
                                                aov_separator)
        if prefix.lower() != default_prefix.lower():
            cls.log.warning("Warning: prefix differs from "
                            "recommended {}".format(default_prefix))
            invalid = True

        if padding != cls.DEFAULT_PADDING:
            invalid = True
            cls.log.error("Expecting padding of {} ( {} )".format(
                cls.DEFAULT_PADDING, "0" * cls.DEFAULT_PADDING))

        # Validate render setup include all lights
        settings_lights_flag = render_settings.get("enable_all_lights", False)
        instance_lights_flag = instance.data.get("renderSetupIncludeLights")
        if settings_lights_flag != instance_lights_flag:
            cls.log.warning(
                "Instance flag for \"Render Setup Include Lights\" is set to "
                "{} and Settings flag is set to {}".format(
                    instance_lights_flag, settings_lights_flag
                )
            )

        # go through definitions and test if such node.attribute exists.
        # if so, compare its value from the one required.
        for data in cls.get_nodes(instance, renderer):
            for node in data["nodes"]:
                try:
                    render_value = cmds.getAttr(
                        "{}.{}".format(node, data["attribute"])
                    )
                except PublishValidationError:
                    invalid = True
                    cls.log.error(
                        "Cannot get value of {}.{}".format(
                            node, data["attribute"]
                        )
                    )
                else:
                    if render_value not in data["values"]:
                        invalid = True
                        cls.log.error(
                            "Invalid value {} set on {}.{}. Expecting "
                            "{}".format(
                                render_value,
                                node,
                                data["attribute"],
                                data["values"]
                            )
                        )

        return invalid

    @classmethod
    def get_nodes(cls, instance, renderer):
        maya_settings = instance.context.data["project_settings"]["maya"]
        validation_settings = (
            maya_settings["publish"]["ValidateRenderSettings"].get(
                "{}_render_attributes".format(renderer)
            ) or []
        )

        result = []
        for attr, values in OrderedDict(validation_settings).items():
            values = [convert_to_int_or_float(v) for v in values if v]

            # Validate the settings has values.
            if not values:
                cls.log.error(
                    "Settings for {} is missing values.".format(attr)
                )
                continue

            if "." not in attr:
                cls.log.warning("Skipping invalid attribute defined in "
                                "validation settings: '{}'".format(attr))
                continue

            node_type, attribute_name = attr.split(".", 1)
            nodes = cmds.ls(type=node_type)
            if not nodes:
                cls.log.warning(
                    "No nodes of type '{}' found.".format(node_type))
                continue

            result.append(
                {
                    "attribute": attribute_name,
                    "nodes": nodes,
                    "values": values
                }
            )

        for attr, required_value in cls._required_globals.items():
            result.append({
                "attribute": attr,
                "nodes": ["defaultRenderGlobals"],
                "values": [required_value]
            })

        return result

    @classmethod
    def repair(cls, instance):
        renderer = instance.data['renderer']
        layer_node = instance.data['setMembers']

        # Apply attribute differences
        # TODO: This sets values even for the correct attributes which
        #  is not what we'd want if it's matching ANY of the correct values
        for data in cls.get_nodes(instance, renderer):
            if not data["values"]:
                continue
            for node in data["nodes"]:
                lib.set_attribute(data["attribute"], data["values"][0], node)

        # Apply render settings
        render_settings = RenderSettings(
            project_settings=instance.context.data["project_settings"])

        default_prefix = render_settings.get_default_image_prefix(renderer)
        aov_separator = render_settings.get_aov_separator()

        with lib.renderlayer(layer_node):

            # Repair animation must be enabled
            cmds.setAttr("defaultRenderGlobals.animation", True)

            # Repair prefix
            if renderer == "arnold":
                multipart = cmds.getAttr("defaultArnoldDriver.mergeAOVs")
                if multipart:
                    separator_variations = [
                        "_<RenderPass>",
                        "<RenderPass>_",
                        "<RenderPass>",
                    ]
                    for variant in separator_variations:
                        default_prefix = default_prefix.replace(variant, "")

            if renderer != "renderman":
                prefix_attr = render_settings.get_image_prefix_attr(renderer)
                cmds.setAttr(prefix_attr, default_prefix, type="string")

                # Repair padding
                padding_attr = render_settings.get_padding_attr(renderer)
                cmds.setAttr(padding_attr, cls.DEFAULT_PADDING)
            else:
                # renderman handles stuff differently
                cmds.setAttr("rmanGlobals.imageFileFormat",
                             default_prefix,
                             type="string")
                cmds.setAttr("rmanGlobals.imageOutputDir",
                             cls.renderman_dir_prefix,
                             type="string")

            # Repair AOV separators
            if renderer == "vray":
                vray_settings = cmds.ls(type="VRaySettingsNode")
                if not vray_settings:
                    node = cmds.createNode("VRaySettingsNode")
                else:
                    node = vray_settings[0]

                cmds.optionMenuGrp("vrayRenderElementSeparator",
                                   v=aov_separator)
                cmds.setAttr(
                    "{}.fileNameRenderElementSeparator".format(node),
                    aov_separator,
                    type="string"
                )

            if renderer == "redshift":
                redshift_AOV_prefix = cls.redshift_AOV_prefix.replace(
                    "{aov_separator}", aov_separator
                )
                # get redshift AOVs
                rs_aovs = cmds.ls(type="RedshiftAOV", referencedNodes=False)
                for aov in rs_aovs:
                    # fix AOV prefixes
                    cmds.setAttr("{}.filePrefix".format(aov),
                                 redshift_AOV_prefix,
                                 type="string")
                    # fix AOV file format
                    default_ext = cmds.getAttr("redshiftOptions.imageFormat",
                                               asString=True)
                    cmds.setAttr("{}.fileFormat".format(aov),
                                 default_ext)
