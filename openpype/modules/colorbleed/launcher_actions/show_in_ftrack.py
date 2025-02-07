"""
Example Ftrack URL:

https://pype.ftrackapp.com/#slideEntityId=38c5fec4-0aed-11ea-a454-3e41ec9bc0d6&slideEntityType=show&view=tasks&itemId=projects&entityId=38c5fec4-0aed-11ea-a454-3e41ec9bc0d6&entityType=show

# This is required otherwise is url invalid view=tasks&itemId=projects&entityId=38c5fec4-0aed-11ea-a454-3e41ec9bc0d6&entityType=show

- "itemId=projects" the top category (overview / projects/ reports / ...)
    must be 'projects'
- "view=tasks" view category 'tasks' is best
- "entityId=38c5fec4-0aed-11ea-a454-3e41ec9bc0d6" id of entity which is in focus (project id is easiest)
- "entityType=show" entity type of 'entityId'

Entity detail in slide (on right side) can't be used on it's own: slideEntityId=38c5fec4-0aed-11ea-a454-3e41ec9bc0d6&slideEntityType=show
- "slideEntityId=38c5fec4-0aed-11ea-a454-3e41ec9bc0d6" entity id which is showed in detail
- "slideEntityType=show" type of 'slideEntityId' entity

Warning: entityType is not entity_type!
    entityType "show" == entity_type "Project"
    entityType "task" == entity_type "Task", "Shot", "Library", "Folder", ...

"""
import webbrowser

from openpype.pipeline import LauncherAction
from openpype.modules import ModulesManager
from openpype.client import get_project, get_asset_by_name


class ShowInFtrack(LauncherAction):
    name = "showinftrack"
    label = "Show in Ftrack"
    icon = "external-link-square"
    color = "#e0e1e1"
    order = 10

    @staticmethod
    def get_ftrack_module():
        return ModulesManager().modules_by_name.get("ftrack")

    def is_compatible(self, session):
        if not session.get("AVALON_PROJECT"):
            return False

        ftrack_module = self.get_ftrack_module()
        if not ftrack_module or not ftrack_module.enabled:
            return False

        return True

    def process(self, session, **kwargs):

        ftrack_module = self.get_ftrack_module()
        ftrack_url = ftrack_module.ftrack_url

        # Context inputs
        project_name = session["AVALON_PROJECT"]
        asset_name = session.get("AVALON_ASSET", None)
        # TODO: implement task entity support?
        # task_name = session.get("AVALON_TASK", None)

        fields = ["data.ftrackId"]
        project = get_project(project_name=project_name,
                              fields=fields)
        if not project:
            raise RuntimeError(f"Project {project_name} not found.")

        project_ftrack_id = project["data"].get("ftrackId")
        if not project_ftrack_id:
            raise RuntimeError(f"Project {project_name} has no "
                               f"connected ftrack id.")

        asset_ftrack_id = None
        if asset_name:
            asset = get_asset_by_name(project_name,
                                      asset_name=asset_name,
                                      fields=
                                      fields)
            asset_ftrack_id = asset["data"].get("ftrackId")

        # Construct the ftrack URL
        # Required
        data = {
            "itemId": "projects",
            "view": "tasks",
            "entityId": project_ftrack_id,
            "entityType": "show"
        }

        # Optional slide
        if asset_ftrack_id:
            data.update({
                "slideEntityId": asset_ftrack_id,
                "slideEntityType": "task"
            })

        sub_url = "&".join("{}={}".format(key, value) for
                           key, value in data.items())
        url = f"{ftrack_url}/#{sub_url}"

        # Open URL in webbrowser
        self.log.info(f"Opening URL: {url}")
        webbrowser.open(url,
                        # Try in new tab
                        new=2)
