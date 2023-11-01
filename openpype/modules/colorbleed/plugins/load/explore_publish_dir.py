from openpype.lib import is_running_from_build

import os
import subprocess
import platform

from openpype.pipeline import load


class ShowPublishInExplorer(load.LoaderPlugin):
    """Debug context data of representation"""

    families = ["*"]
    representations = ["*"]

    enabled = (
        not is_running_from_build() or
        os.getenv("OPENPYPE_DEBUG") == "1"
    )

    label = "Show in explorer"
    order = 100
    icon = "external-link"
    color = "gray"

    def load(self, context, name, namespace, data):

        path = self.filepath_from_context(context)
        self.open_in_explorer(os.path.dirname(path))

    @staticmethod
    def open_in_explorer(path):
        platform_name = platform.system().lower()
        if platform_name == "windows":
            args = ["start", path]
        elif platform_name == "darwin":
            args = ["open", "-na", path]
        elif platform_name == "linux":
            args = ["xdg-open", path]
        else:
            raise RuntimeError(f"Unknown platform {platform.system()}")
        # Make sure path is converted correctly for 'os.system'
        os.system(subprocess.list2cmdline(args))
