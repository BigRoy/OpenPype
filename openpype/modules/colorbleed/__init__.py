import os

from openpype.modules import OpenPypeAddOn
from openpype.modules.interfaces import IPluginPaths


class ColorbleedModule(OpenPypeAddOn, IPluginPaths):
    name = "colorbleed"

    def get_plugin_paths(self):
        """Implementation of IPluginPaths to get plugin paths."""
        current_dir = os.path.dirname(os.path.abspath(__file__))

        return {
            "actions": [os.path.join(current_dir, "launcher_actions")],
            "load": [os.path.join(current_dir, "plugins", "load")],
            "publish": [os.path.join(current_dir, "plugins", "publish")]
        }
