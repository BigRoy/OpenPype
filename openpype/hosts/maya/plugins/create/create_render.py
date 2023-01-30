# -*- coding: utf-8 -*-
"""Create ``Render`` instance in Maya."""
from maya import cmds
from maya.app.renderSetup.model import renderSetup

from openpype.hosts.maya.api import (
    lib,
    lib_rendersettings,
    plugin
)
from openpype.lib import (
    BoolDef,
    NumberDef
)

from openpype.pipeline import legacy_io
from openpype.pipeline.create import (
    CreatorError,
    Creator,
    HiddenCreator,
    CreatedInstance
)


def ensure_namespace(namespace):
    """Make sure the namespace exists.

    Args:
        namespace (str): The preferred namespace name.

    Returns:
        str: The generated or existing namespace

    """
    exists = cmds.namespace(exists=namespace)
    if exists:
        return namespace
    else:
        return cmds.namespace(add=namespace)


class CreateRender(Creator):
    """Create *render* instance.

    This render instance is not visible in the UI as an instance nor does
    it by itself publish. Instead, whenever this is created the
    CreateRenderlayer creator collects the active scene's actual renderlayers
    as individual instances to submit for publishing.

    This Creator is solely to SHOW in the "Create" of the new publisher.

    See Also:
        https://pype.club/docs/artist_hosts_maya#creating-basic-render-setup

    """

    identifier = "io.openpype.creators.maya.render"
    label = "Render"
    family = "rendering"
    icon = "eye"

    render_settings = {}

    @classmethod
    def apply_settings(cls, project_settings, system_settings):
        cls.render_settings = project_settings["maya"]["RenderSettings"]

    def create(self, subset_name, instance_data, pre_create_data):

        # Only allow a single render instance to exist
        nodes = lib.lsattr("pre_creator_identifier", self.identifier)
        if nodes:
            raise CreatorError("A Render instance already exists - only "
                               "one can be configured.")

        # Apply default project render settings on create
        if self.render_settings.get("apply_render_settings"):
            lib_rendersettings.RenderSettings().set_default_renderer_settings()

        # if no render layers are present, create default one with
        # asterisk selector
        rs = renderSetup.instance()
        if not rs.getRenderLayers():
            render_layer = rs.createRenderLayer('Main')
            collection = render_layer.createCollection("defaultCollection")
            collection.getSelector().setPattern('*')

        with lib.undo_chunk():
            node = cmds.sets(empty=True, name=subset_name)
            lib.imprint(node, data={
                "pre_creator_identifier": self.identifier
            })

            # By RenderLayerCreator.create we make it so that the renderlayer
            # instances directly appear even though it just collects scene
            # renderlayers. This doesn't actually 'create' any scene contents.
            self.create_context.create(
                CreateRenderlayer.identifier,
                instance_data={},
                source_data=instance_data
            )

    def collect_instances(self):
        # We never show this instance in the publish UI
        return

    def update_instances(self, update_list):
        return

    def remove_instances(self, instances):
        return


class CreateRenderlayer(HiddenCreator, plugin.MayaCreatorBase):
    """Create and manges renderlayer subset per renderLayer in workfile.

    This does no do ANYTHING until a CreateRender subset exists in the
    scene, created by the CreateRender creator.

    """

    identifier = "io.openpype.creators.maya.renderlayer"
    family = "renderlayer"
    label = "Renderlayer"
    icon = "eye"

    enable_all_lights = False

    @classmethod
    def apply_settings(cls, project_settings, system_settings):
        render_settings = project_settings["maya"]["RenderSettings"]
        cls.enable_all_lights = render_settings.get("enable_all_lights",
                                                    cls.enable_all_lights)

    def create(self, instance_data, source_data):
        # A Renderlayer is never explicitly created using the create method.
        # Instead, renderlayers from the scene are collected. Thus "create"
        # would only ever be called to say, 'hey, please refresh collect'
        self.collect_instances()

    def collect_instances(self):

        # We only collect if a CreateRender instance exists
        if not lib.lsattr("pre_creator_identifier", CreateRender.identifier):
            return

        rs = renderSetup.instance()
        layers = rs.getRenderLayers()
        for layer in layers:
            layer_instance_node = self.find_layer_instance_node(layer)
            if layer_instance_node:
                data = self.read_instance_node(layer_instance_node)
                instance = CreatedInstance.from_existing(data, creator=self)
            else:
                subset_name = "render" + layer.name()

                instance_data = {
                    "asset": legacy_io.Session["AVALON_ASSET"],
                    "task": legacy_io.Session["AVALON_TASK"],
                    "variant": layer.name(),
                }

                instance = CreatedInstance(
                    family=self.family,
                    subset_name=subset_name,
                    data=instance_data,
                    creator=self
                )
            instance.transient_data["layer"] = layer
            self._add_instance_to_context(instance)

    def find_layer_instance_node(self, layer):
        connected_sets = cmds.listConnections(
            "{}.message".format(layer.name()),
            source=False,
            destination=True,
            type="objectSet"
        ) or []

        for node in connected_sets:
            if not cmds.attributeQuery("creator_identifier",
                                       node=node,
                                       exists=True):
                continue

            creator_identifier = cmds.getAttr(node + ".creator_identifier")
            if creator_identifier == self.identifier:
                print(f"Found node: {node}")
                return node

    def _create_layer_instance_node(self, layer):

        # We only collect if a CreateRender instance exists
        create_render_sets = lib.lsattr("pre_creator_identifier",
                                        CreateRender.identifier)
        if not create_render_sets:
            raise CreatorError("Creating a renderlayer instance node is not "
                               "allowed if no 'CreateRender' instance exists")
        create_render_set = create_render_sets[0]

        namespace = "_renderingMain"
        namespace = ensure_namespace(namespace)

        name = "{}:{}".format(namespace, layer.name())
        render_set = cmds.sets(name=name, empty=True)

        # Keep an active link with the renderlayer so we can retrieve it
        # later by a physical maya connection instead of relying on the layer
        # name to still exist
        cmds.addAttr(render_set, longName="renderlayer", at="message")
        cmds.connectAttr(layer.name() + ".message",
                         render_set + ".renderlayer", force=True)

        # Add the set to the 'CreateRender' set.
        cmds.sets(render_set, forceElement=create_render_set)

        return render_set

    def update_instances(self, update_list):
        # We only generate the persisting layer data into the scene once
        # we save with the UI on e.g. validate or publish
        for instance, _changes in update_list:
            instance_node = instance.data.get("instance_node")

            # Ensure a node to persist the data to exists
            if not instance_node:
                layer = instance.transient_data["layer"]
                instance_node = self._create_layer_instance_node(layer)
                instance.data["instance_node"] = instance_node
            else:
                # TODO: Keep name in sync with the actual renderlayer?
                pass

            self.imprint_instance_node(instance_node,
                                       data=instance.data_to_store())

    def remove_instances(self, instances):
        """Remove specified instance from the scene.

        This is only removing `id` parameter so instance is no longer
        instance, because it might contain valuable data for artist.

        """
        # Instead of removing the single instance or renderlayers we instead
        # remove the CreateRender node this creator relies on to decide whether
        # it should collect anything at all.
        nodes = lib.lsattr("pre_creator_identifier", CreateRender.identifier)
        if nodes:
            cmds.delete(nodes)

        # Remove ALL of the instances even if only one gets deleted
        for instance in list(self.create_context.instances):
            if instance.get("creator_identifier") == self.identifier:
                self._remove_instance_from_context(instance)

                # Remove the stored settings per renderlayer too
                node = instance.data.get("instance_node")
                if node and cmds.objExists(node):
                    cmds.delete(node)

    def get_instance_attr_defs(self):
        """Create instance settings."""

        return [
            BoolDef("review",
                    label="Review",
                    tooltip="Mark as reviewable",
                    default=True),
            BoolDef("extendFrames",
                    label="Extend Frames",
                    tooltip="Extends the frames on top of the previous "
                            "publish.\nIf the previous was 1001-1050 and you "
                            "would now submit 1020-1070 only the new frames "
                            "1051-1070 would be rendered and published "
                            "together with the previously rendered frames.\n"
                            "If 'overrideExistingFrame' is enabled it *will* "
                            "render any existing frames.",
                    default=False),
            BoolDef("overrideExistingFrame",
                    label="Override Existing Frame",
                    tooltip="Mark as reviewable",
                    default=True),

            # TODO: Should these move to submit_maya_deadline plugin?
            # Tile rendering
            BoolDef("tileRendering",
                    label="Enable tiled rendering",
                    default=False),
            NumberDef("tilesX",
                      label="Tiles X",
                      default=2,
                      minimum=1,
                      decimals=0),
            NumberDef("tilesY",
                      label="Tiles Y",
                      default=2,
                      minimum=1,
                      decimals=0),

            # Additional settings
            BoolDef("convertToScanline",
                    label="Convert to Scanline",
                    tooltip="Convert the output images to scanline images",
                    default=False),
            BoolDef("useReferencedAovs",
                    label="Use Referenced AOVs",
                    tooltip="Consider the AOVs from referenced scenes as well",
                    default=False),

            BoolDef("renderSetupIncludeLights",
                    label="Render Setup Include Lights",
                    default=self.enable_all_lights)
        ]
