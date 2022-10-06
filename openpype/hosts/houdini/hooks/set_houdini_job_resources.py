import os
from openpype.lib import PreLaunchHook


class HoudiniSetJobResourcesEnvs(PreLaunchHook):
    """Set environment variable JOB and HOUDINI_OTLSCAN_PATH.

    Hook `GlobalHostDataHook` must be executed before this hook.

    """
    app_groups = ["houdini"]

    def execute(self):
        workdir = self.launch_context.env.get("AVALON_WORKDIR", "")
        if not workdir:
            self.log.warning("BUG: Workdir is not filled.")
            return

        work_root = str(self.data["anatomy"].roots["work"])
        project_name = self.data["project_name"]

        project_root_work = os.path.join(work_root, project_name)
        project_resources = os.path.join(project_root_work, "resources")
        project_resource_otls = os.path.join(project_resources, "otls")

        self.launch_context.env.update({
            "JOB": f"{project_resources}",
            "HOUDINI_OTLSCAN_PATH": f"{project_resource_otls};&"
        })
