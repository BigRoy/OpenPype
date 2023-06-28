import os

from openpype.modules import OpenPypeModule
from openpype.modules.interfaces import IPluginPaths


class ColorbleedModule(OpenPypeModule, IPluginPaths):
    name = "colorbleed"

    def initialize(self, modules_settings):
        self.enabled = True

    def get_plugin_paths(self):
        """Implementation of IPluginPaths to get plugin paths."""
        current_dir = os.path.dirname(os.path.abspath(__file__))

        return {
            "actions": [os.path.join(current_dir, "launcher_actions")],
            "publish": [os.path.join(current_dir, "plugins", "publish")]
        }
