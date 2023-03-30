# -*- coding: utf-8 -*-
"""Creator plugin for creating pointcache alembics."""
from openpype.hosts.houdini.api import plugin
from openpype.pipeline import CreatedInstance
from openpype.lib import EnumDef, BoolDef, NumberDef


class CreateReview(plugin.HoudiniCreator):
    """Review with OpenGL ROP"""

    identifier = "io.openpype.creators.houdini.review"
    label = "Review"
    family = "review"
    icon = "video-camera"

    def create(self, subset_name, instance_data, pre_create_data): # type: CreatedInstance
        import hou

        instance_data.pop("active", None)
        instance_data.update({"node_type": "opengl"})
        instance_data["imageFormat"] = pre_create_data.get("imageFormat")
        instance_data["keepImages"] = pre_create_data.get("keepImages")

        instance = super(CreateReview, self).create(
            subset_name,
            instance_data,
            pre_create_data)

        instance_node = hou.node(instance.get("instance_node"))

        frame_range = hou.playbar.frameRange()

        parms = {
            "picture": "{}{}".format(
            hou.text.expandString("$HIP/pyblish/"),
            "{}/{}.$F4.{}".format(
                subset_name,
                subset_name,
                pre_create_data.get("image_format") or "png")),
            "trange": 1,
            "f1": frame_range[0],
            "f2": frame_range[1],
        }

        override_resolution = pre_create_data.get("override_resolution")
        if override_resolution:
            parms.update({
                "tres": override_resolution,
                "res1": pre_create_data.get("resx"),
                "res2": pre_create_data.get("resy"),
                "aspect": pre_create_data.get("aspect"),
            })

        if self.selected_nodes:
            # todo: allow only object paths?
            node_paths = " ".join(node.path() for node in self.selected_nodes)
            parms.update({"scenepath": node_paths})

        instance_node.setParms(parms)

        to_lock = ["id", "family"]

        self.lock_parameters(instance_node, to_lock)

    def get_pre_create_attr_defs(self):
        attrs = super().get_pre_create_attr_defs()
        image_format_enum = [
            {
                "value": "png",
                "label": ".png"
            },
            {
                "value": "tif",
                "label": ".tif"
            },
            {
                "value": "sgi",
                "label": ".sgi"
            },
            {
                "value": "pic.gz",
                "label": ".pic.gz"
            },
            {
                "value": "rat",
                "label": ".rat"
            },
            {
                "value": "jpg",
                "label": ".jpg"
            },
            {
                "value": "cin",
                "label": ".cin"
            },
            {
                "value": "rta",
                "label": ".rta"
            },
            {
                "value": "rat",
                "label": ".rat"
            },
            {
                "value": "bmp",
                "label": ".bmp"
            },
            {
                "value": "tga",
                "label": ".tga"
            },
            {
                "value": "rad",
                "label": ".rad"
            },
            {
                "value": "exr",
                "label": ".exr"
            },
            {
                "value": "pic",
                "label": ".pic"
            }
        ]

        return attrs + [
            BoolDef("keepImages",
                    label="Keep Image Sequences",
                    default=False),
            EnumDef("imageFormat",
                    image_format_enum,
                    label="Image Format Options"),
            BoolDef("override_resolution",
                    label="Override resolution",
                    tooltip="When disabled the resolution set on the camera "
                            "is used instead.",
                    default=True),
            NumberDef("resx",
                      label="Resolution Width",
                      default=1280,
                      minimum=2,
                      decimals=0),
            NumberDef("resy",
                      label="Resolution Height",
                      default=720,
                      minimum=2,
                      decimals=0),
            NumberDef("aspect",
                      label="Aspect Ratio",
                      default=1.0,
                      minimum=0.0001,
                      decimals=3)
        ]
