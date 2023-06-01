import pyblish.api
from openpype.hosts.cinema4d import api


class CollectCinema4DCurrentFile(pyblish.api.ContextPlugin):
    """Inject the current working file into context"""

    order = pyblish.api.CollectorOrder - 0.5
    label = "Cinema4D Current File"
    hosts = ['cinema4d']

    def process(self, context):
        """Inject the current working file"""

        context.data['currentFile'] = api.current_file()

        assert api.current_file() != '', (
            "Current file is not saved. Save the file before continuing."
        )
