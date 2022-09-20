"""
Basic avalon integration
"""
import os
import re
import sys
import json
import logging
import tempfile

import pyblish.api

from openpype.lib import (
    Logger,
    register_event_callback
)
from openpype.pipeline import (
    register_loader_plugin_path,
    register_creator_plugin_path,
    register_inventory_action_path,
    deregister_loader_plugin_path,
    deregister_creator_plugin_path,
    deregister_inventory_action_path,
    AVALON_CONTAINER_ID,
    legacy_io
)
from openpype.client import get_asset_by_name
from openpype.pipeline.context_tools import (
    change_current_context,
    compute_session_changes
)
from openpype.pipeline.load import any_outdated_containers
from openpype.hosts.fusion import FUSION_HOST_DIR
from openpype.tools.utils import host_tools

from .lib import (
    get_current_comp,
    comp_lock_and_undo_chunk,
    validate_comp_prefs
)

log = Logger.get_logger(__name__)

PLUGINS_DIR = os.path.join(FUSION_HOST_DIR, "plugins")

PUBLISH_PATH = os.path.join(PLUGINS_DIR, "publish")
LOAD_PATH = os.path.join(PLUGINS_DIR, "load")
CREATE_PATH = os.path.join(PLUGINS_DIR, "create")
INVENTORY_PATH = os.path.join(PLUGINS_DIR, "inventory")


class CompLogHandler(logging.Handler):
    def emit(self, record):
        entry = self.format(record)
        fusion = getattr(sys.modules["__main__"], "fusion", None)
        if fusion:
            fusion.Print(entry)


def install():
    """Install fusion-specific functionality of avalon-core.

    This is where you install menus and register families, data
    and loaders into fusion.

    It is called automatically when installing via
    `openpype.pipeline.install_host(openpype.hosts.fusion.api)`

    See the Maya equivalent for inspiration on how to implement this.

    """
    # Remove all handlers associated with the root logger object, because
    # that one sometimes logs as "warnings" incorrectly.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Attach default logging handler that prints to active comp
    logger = logging.getLogger()
    formatter = logging.Formatter(fmt="%(message)s\n")
    handler = CompLogHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    log.info("openpype.hosts.fusion installed")

    pyblish.api.register_host("fusion")
    pyblish.api.register_plugin_path(PUBLISH_PATH)
    log.info("Registering Fusion plug-ins..")

    register_loader_plugin_path(LOAD_PATH)
    register_creator_plugin_path(CREATE_PATH)
    register_inventory_action_path(INVENTORY_PATH)

    pyblish.api.register_callback(
        "instanceToggled", on_pyblish_instance_toggled
    )

    # Fusion integration currently does not attach to direct callbacks of
    # the application. So we use workfile callbacks to allow similar behavior
    # on save and open
    register_event_callback("workfile.open.after", on_after_workfile_open)
    register_event_callback("workfile.save.after", on_after_workfile_save)


def uninstall():
    """Uninstall all that was installed

    This is where you undo everything that was done in `install()`.
    That means, removing menus, deregistering families and  data
    and everything. It should be as though `install()` was never run,
    because odds are calling this function means the user is interested
    in re-installing shortly afterwards. If, for example, he has been
    modifying the menu or registered families.

    """
    pyblish.api.deregister_host("fusion")
    pyblish.api.deregister_plugin_path(PUBLISH_PATH)
    log.info("Deregistering Fusion plug-ins..")

    deregister_loader_plugin_path(LOAD_PATH)
    deregister_creator_plugin_path(CREATE_PATH)
    deregister_inventory_action_path(INVENTORY_PATH)

    pyblish.api.deregister_callback(
        "instanceToggled", on_pyblish_instance_toggled
    )


def on_pyblish_instance_toggled(instance, old_value, new_value):
    """Toggle saver tool passthrough states on instance toggles."""
    comp = instance.context.data.get("currentComp")
    if not comp:
        return

    savers = [tool for tool in instance if
              getattr(tool, "ID", None) == "Saver"]
    if not savers:
        return

    # Whether instances should be passthrough based on new value
    passthrough = not new_value
    with comp_lock_and_undo_chunk(comp,
                                  undo_queue_name="Change instance "
                                                  "active state"):
        for tool in savers:
            attrs = tool.GetAttrs()
            current = attrs["TOOLB_PassThrough"]
            if current != passthrough:
                tool.SetAttrs({"TOOLB_PassThrough": passthrough})


def on_after_workfile_save(_event):
    comp = get_current_comp()
    CompSessions.instance().register_comp_session(comp)


def on_after_workfile_open(_event):
    comp = get_current_comp()
    CompSessions.instance().register_comp_session(comp)

    validate_comp_prefs(comp)

    if any_outdated_containers():
        log.warning("Scene has outdated content.")

        # Find OpenPype menu to attach to
        from . import menu

        def _on_show_scene_inventory():
            # ensure that comp is active
            frame = comp.CurrentFrame
            if not frame:
                print("Comp is closed, skipping show scene inventory")
                return
            frame.ActivateFrame()   # raise comp window
            host_tools.show_scene_inventory()

        from openpype.widgets import popup
        from openpype.style import load_stylesheet
        dialog = popup.Popup(parent=menu.menu)
        dialog.setWindowTitle("Fusion comp has outdated content")
        dialog.setMessage("There are outdated containers in "
                          "your Fusion comp.")
        dialog.on_clicked.connect(_on_show_scene_inventory)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        dialog.setStyleSheet(load_stylesheet())


def ls():
    """List containers from active Fusion scene

    This is the host-equivalent of api.ls(), but instead of listing
    assets on disk, it lists assets already loaded in Fusion; once loaded
    they are called 'containers'

    Yields:
        dict: container

    """

    comp = get_current_comp()
    tools = comp.GetToolList(False, "Loader").values()

    for tool in tools:
        container = parse_container(tool)
        if container:
            yield container


def imprint_container(tool,
                      name,
                      namespace,
                      context,
                      loader=None):
    """Imprint a Loader with metadata

    Containerisation enables a tracking of version, author and origin
    for loaded assets.

    Arguments:
        tool (object): The node in Fusion to imprint as container, usually a
            Loader.
        name (str): Name of resulting assembly
        namespace (str): Namespace under which to host container
        context (dict): Asset information
        loader (str, optional): Name of loader used to produce this container.

    Returns:
        None

    """

    data = [
        ("schema", "openpype:container-2.0"),
        ("id", AVALON_CONTAINER_ID),
        ("name", str(name)),
        ("namespace", str(namespace)),
        ("loader", str(loader)),
        ("representation", str(context["representation"]["_id"])),
    ]

    for key, value in data:
        tool.SetData("avalon.{}".format(key), value)


def parse_container(tool):
    """Returns imprinted container data of a tool

    This reads the imprinted data from `imprint_container`.

    """

    data = tool.GetData('avalon')
    if not isinstance(data, dict):
        return

    # If not all required data return the empty container
    required = ['schema', 'id', 'name',
                'namespace', 'loader', 'representation']
    if not all(key in data for key in required):
        return

    container = {key: data[key] for key in required}

    # Store the tool's name
    container["objectName"] = tool.Name

    # Store reference to the tool object
    container["_tool"] = tool

    return container


class CompSessions(object):
    """Store and retrieve OpenPype Session per Comp

    For the current app id (unique like process id) we produce a temporary
    json file in which we can store an OpenPype Session per comp. Using that
    Session we know what "AVALON_ASSET", "AVALON_TASK", etc. the comp was
    related to.

    The Sessions are stored as:
    {
        "{comp_id1}": SESSION1,
        "{comp_id2}": SESSION2,
    }

    Where SESSION is a copy of a `legacy_io.Session` reduced to only the
        AVALON_PROJECT, AVALON_ASSET, AVALON_TASK

    """
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):

        uuid = self.get_fusion_id()
        folder = tempfile.gettempdir()
        fname = "fusion_{uuid}.json".format(uuid=uuid)
        self._path = os.path.join(folder, fname)
        self._cached = {}

    def get_comp_sessions(self):
        import json
        if not os.path.exists(self._path):
            return {}

        with open(self._path, "r") as f:
            data = json.load(f)

        self._cached.update(data)
        return data

    def register_comp_session(self, comp, session=None):
        if session is None:
            session = legacy_io.Session

        comp_id = self.get_comp_id(comp)
        data = self.get_comp_sessions()

        # Store only a project, asset and task of the session
        session_reduced = {
            "AVALON_PROJECT": session["AVALON_PROJECT"],
            "AVALON_ASSET": session["AVALON_ASSET"],
            "AVALON_TASK": session["AVALON_TASK"]
        }
        data[comp_id] = session_reduced

        with open(self._path, "w") as f:
            json.dump(data, f)

    def get_comp_session(self, comp, allow_cache=True):
        comp_id = self.get_comp_id(comp)
        if allow_cache and comp_id in self._cached:
            return self._cached[comp_id]

        return self.get_comp_sessions().get(comp_id)

    def delete(self):
        # Delete sessions cache file
        if os.path.isfile(self._path):
            os.remove(self._path)
        self._cached.clear()

    def apply_comp_session(self, session):

        project_name = session.get("AVALON_PROJECT")
        asset_name = session.get("AVALON_ASSET")
        task_name = session.get("AVALON_TASK")
        if not project_name or not asset_name or not task_name:
            return False
        asset_doc = get_asset_by_name(project_name, asset_name=asset_name)
        if not asset_doc:
            return False

        changes = compute_session_changes(legacy_io.Session,
                                          asset_doc=asset_doc,
                                          task_name=task_name)
        if not changes:
            return False

        change_current_context(
            asset_doc=asset_doc,
            task_name=session["AVALON_ASSET"],
            template_key="work"
        )
        return True

    @staticmethod
    def get_fusion_id():
        # Get UUID from connected fusion instance
        fusion = getattr(sys.modules["__main__"], "fusion", None)
        match = re.search(r"UUID: (.*)\]$", str(fusion))
        uuid = match.group(1)
        return uuid

    @staticmethod
    def get_comp_id(comp):
        return str(comp).split("(", 1)[1].split(")", 1)[0]
