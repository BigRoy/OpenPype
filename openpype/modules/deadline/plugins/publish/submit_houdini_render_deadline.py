import os
import attr
import getpass
from datetime import datetime

import pyblish.api

from openpype.pipeline import legacy_io, OpenPypePyblishPluginMixin
from openpype.tests.lib import is_in_tests
from openpype_modules.deadline import abstract_submit_deadline
from openpype_modules.deadline.abstract_submit_deadline import DeadlineJobInfo
from openpype.lib import (
    is_running_from_build,
    NumberDef
)


@attr.s
class DeadlinePluginInfo():
    SceneFile = attr.ib(default=None)
    OutputDriver = attr.ib(default=None)
    Version = attr.ib(default=None)
    IgnoreInputs = attr.ib(default=True)


@attr.s
class ArnoldRenderDeadlinePluginInfo():
    InputFile = attr.ib(default=None)
    Verbose = attr.ib(default=4)


@attr.s
class MantraRenderDeadlinePluginInfo():
    SceneFile = attr.ib(default=None)
    Version = attr.ib(default=None)


@attr.s
class VrayRenderPluginInfo():
    InputFilename = attr.ib(default=None)
    SeparateFilesPerFrame = attr.ib(default=True)


@attr.s
class RedshiftRenderPluginInfo():
    SceneFile = attr.ib(default=None)
    Version = attr.ib(default=None)


@attr.s
class HuskStandalonePluginInfo():
    """Requires Deadline Husk Standalone Plugin.

    See Deadline Plug-in:
        https://github.com/DavidTree/HuskStandaloneSubmitter

    Also see Husk options here:
        https://www.sidefx.com/docs/houdini/ref/utils/husk.html

    """
    SceneFile = attr.ib()
    # TODO: Below parameters are only supported by custom version of the plugin
    Renderer = attr.ib(default=None)
    RenderSettings = attr.ib(default="/Render/rendersettings")
    Purpose = attr.ib(default="geometry,render")
    Complexity = attr.ib(default="veryhigh")
    Snapshot = attr.ib(default=-1)
    LogLevel = attr.ib(default="2")
    PreRender = attr.ib(default="")
    PreFrame = attr.ib(default="")
    PostFrame = attr.ib(default="")
    PostRender = attr.ib(default="")
    RestartDelegate = attr.ib(default="")


class HoudiniSubmitDeadline(
    abstract_submit_deadline.AbstractSubmitDeadline,
    OpenPypePyblishPluginMixin
):
    """Submit Render ROPs to Deadline.

    Renders are submitted to a Deadline Web Service as
    supplied via the environment variable AVALON_DEADLINE.

    Target "local":
        Even though this does *not* render locally this is seen as
        a 'local' submission as it is the regular way of submitting
        a Houdini render locally.

    """

    label = "Submit Render to Deadline"
    order = pyblish.api.IntegratorOrder
    hosts = ["houdini"]
    families = ["redshift_rop",
                "arnold_rop",
                "mantra_rop",
                "karma_rop",
                "vray_rop"]
    targets = ["local"]

    # presets
    priority = 50
    chunk_size = 1
    export_priority = 50
    export_chunk_size = 10
    group = ""
    export_group = ""

    @classmethod
    def get_attribute_defs(cls):
        return [
            NumberDef(
                "priority",
                label="Priority",
                default=cls.priority,
                decimals=0
            ),
            NumberDef(
                "chunk",
                label="Frames Per Task",
                default=cls.chunk_size,
                decimals=0,
                minimum=1,
                maximum=1000
            ),
            NumberDef(
                "export_priority",
                label="Export Priority",
                default=cls.priority,
                decimals=0
            ),
            NumberDef(
                "export_chunk",
                label="Export Frames Per Task",
                default=cls.export_chunk_size,
                decimals=0,
                minimum=1,
                maximum=1000
            )
        ]

    def get_job_info(self, dependency_job_ids=None):

        instance = self._instance
        context = instance.context

        attribute_values = self.get_attr_values_from_data(instance.data)

        # Whether Deadline render submission is being split in two
        # (extract + render)
        split_render_job = instance.data.get("splitRender")

        # If there's some dependency job ids we can assume this is a render job
        # and not an export job
        is_export_job = True
        if dependency_job_ids:
            is_export_job = False

        job_type = "[RENDER]"
        if split_render_job and not is_export_job:
            family = instance.data["family"]
            plugin = {
                "usdrender": "HuskStandalone",
            }.get(family)
            if not plugin:
                # Convert from family to Deadline plugin name
                # i.e., arnold_rop -> Arnold
                plugin = family.replace("_rop", "").capitalize()
        else:
            plugin = "Houdini"
            if split_render_job:
                job_type = "[EXPORT IFD]"

        job_info = DeadlineJobInfo(Plugin=plugin)

        filepath = context.data["currentFile"]
        filename = os.path.basename(filepath)
        job_info.Name = "{} - {} {}".format(filename, instance.name, job_type)
        job_info.BatchName = filename

        job_info.UserName = context.data.get(
            "deadlineUser", getpass.getuser())

        if split_render_job and is_export_job:
            job_info.Priority = attribute_values.get(
                "export_priority", self.export_priority
            )
        else:
            job_info.Priority = attribute_values.get(
                "priority", self.priority
            )

        if is_in_tests():
            job_info.BatchName += datetime.now().strftime("%d%m%Y%H%M%S")

        # Deadline requires integers in frame range
        start = instance.data["frameStartHandle"]
        end = instance.data["frameEndHandle"]
        frames = "{start}-{end}x{step}".format(
            start=int(start),
            end=int(end),
            step=int(instance.data["byFrameStep"]),
        )
        job_info.Frames = frames

        # Make sure we make job frame dependent so render tasks pick up a soon
        # as export tasks are done
        if split_render_job and not is_export_job:
            job_info.IsFrameDependent = bool(instance.data.get(
                "splitRenderFrameDependent", True))

        job_info.Pool = instance.data.get("primaryPool")
        job_info.SecondaryPool = instance.data.get("secondaryPool")
        job_info.Group = self.group
        if split_render_job and is_export_job:
            job_info.ChunkSize = attribute_values.get(
                "export_chunk", self.export_chunk_size
            )
        else:
            job_info.ChunkSize = attribute_values.get(
                "chunk", self.chunk_size
            )

        # Apply render globals, like e.g. data from collect machine list
        render_globals = instance.data.get("renderGlobals", {})
        if render_globals:
            self.log.debug("Applying 'renderGlobals' to job info: %s",
                           render_globals)
            job_info.update(render_globals)

        job_info.Comment = context.data.get("comment")

        keys = [
            "FTRACK_API_KEY",
            "FTRACK_API_USER",
            "FTRACK_SERVER",
            "OPENPYPE_SG_USER",
            "AVALON_PROJECT",
            "AVALON_ASSET",
            "AVALON_TASK",
            "AVALON_APP_NAME",
            "OPENPYPE_DEV",
            "OPENPYPE_LOG_NO_COLORS",
        ]

        # Add OpenPype version if we are running from build.
        if is_running_from_build():
            keys.append("OPENPYPE_VERSION")

        # Add mongo url if it's enabled
        if self._instance.context.data.get("deadlinePassMongoUrl"):
            keys.append("OPENPYPE_MONGO")

        environment = dict({key: os.environ[key] for key in keys
                            if key in os.environ}, **legacy_io.Session)

        for key in keys:
            value = environment.get(key)
            if value:
                job_info.EnvironmentKeyValue[key] = value

        # to recognize render jobs
        job_info.add_render_job_env_var()

        for i, filepath in enumerate(instance.data["files"]):
            dirname = os.path.dirname(filepath)
            fname = os.path.basename(filepath)
            job_info.OutputDirectory += dirname.replace("\\", "/")
            job_info.OutputFilename += fname

        # Add dependencies if given
        if dependency_job_ids:
            job_info.JobDependencies = ",".join(dependency_job_ids)

        return job_info

    def get_plugin_info(self, job_type=None):
        # Not all hosts can import this module.
        import hou

        instance = self._instance
        context = instance.context

        hou_major_minor = hou.applicationVersionString().rsplit(".", 1)[0]

        # Output driver to render
        if job_type == "render":
            family = instance.data.get("family")
            if family == "arnold_rop":
                plugin_info = ArnoldRenderDeadlinePluginInfo(
                    InputFile=instance.data["ifdFile"]
                )
            elif family == "mantra_rop":
                plugin_info = MantraRenderDeadlinePluginInfo(
                    SceneFile=instance.data["ifdFile"],
                    Version=hou_major_minor,
                )
            elif family == "vray_rop":
                plugin_info = VrayRenderPluginInfo(
                    InputFilename=instance.data["ifdFile"],
                )
            elif family == "redshift_rop":
                plugin_info = RedshiftRenderPluginInfo(
                    SceneFile=instance.data["ifdFile"]
                )
            elif family == "usdrender":
                plugin_info = self._get_husk_standalone_plugin_info(instance)
            else:
                self.log.error(
                    "Family '%s' not supported yet to split render job",
                    family
                )
                return
        else:
            driver = hou.node(instance.data["instance_node"])
            plugin_info = DeadlinePluginInfo(
                SceneFile=context.data["currentFile"],
                OutputDriver=driver.path(),
                Version=hou_major_minor,
                IgnoreInputs=True
            )

        return attr.asdict(plugin_info)

    def process(self, instance):
        super(HoudiniSubmitDeadline, self).process(instance)

        # TODO: Avoid the need for this logic here, needed for submit publish
        # Store output dir for unified publisher (filesequence)
        output_dir = os.path.dirname(instance.data["files"][0])
        instance.data["outputDir"] = output_dir

    def _get_husk_standalone_plugin_info(self, instance):
        # Not all hosts can import this module.
        import hou

        # Supply additional parameters from the USD Render ROP
        # to the Husk Standalone Render Plug-in
        rop_node = hou.node(instance.data["instance_node"])
        snapshot_interval = -1
        if rop_node.evalParm("dosnapshot"):
            snapshot_interval = rop_node.evalParm("snapshotinterval")

        restart_delegate = 0
        if rop_node.evalParm("husk_restartdelegate"):
            restart_delegate = rop_node.evalParm("husk_restartdelegateframes")

        rendersettings = (
            rop_node.evalParm("rendersettings")
            or "/Render/rendersettings"
        )
        return HuskStandalonePluginInfo(
            SceneFile=instance.data["ifdFile"],
            Renderer=rop_node.evalParm("renderer"),
            RenderSettings=rendersettings,
            Purpose=rop_node.evalParm("husk_purpose"),
            Complexity=rop_node.evalParm("husk_complexity"),
            Snapshot=snapshot_interval,
            PreRender=rop_node.evalParm("husk_prerender"),
            PreFrame=rop_node.evalParm("husk_preframe"),
            PostFrame=rop_node.evalParm("husk_postframe"),
            PostRender=rop_node.evalParm("husk_postrender"),
            RestartDelegate=restart_delegate
        )


class HoudiniSubmitDeadlineUsdRender(HoudiniSubmitDeadline):
    # Do not use published workfile paths for USD Render ROP because the
    # Export Job doesn't seem to occur using the published path either, so
    # output paths then do not match the actual rendered paths
    use_published = False
    families = ["usdrender"]
