import os
import sys
import re
import contextlib

from qtpy import QtCore

from openpype.lib import Logger
from openpype.pipeline.context_tools import get_current_project_asset
from openpype.pipeline import registered_host
from openpype.pipeline.create import CreateContext

self = sys.modules[__name__]
self._project = None


def update_frame_range(start, end, comp=None, set_render_range=True,
                       handle_start=0, handle_end=0):
    """Set Fusion comp's start and end frame range

    Args:
        start (float, int): start frame
        end (float, int): end frame
        comp (object, Optional): comp object from fusion
        set_render_range (bool, Optional): When True this will also set the
            composition's render start and end frame.
        handle_start (float, int, Optional): frame handles before start frame
        handle_end (float, int, Optional): frame handles after end frame

    Returns:
        None

    """

    if not comp:
        comp = get_current_comp()

    # Convert any potential none type to zero
    handle_start = handle_start or 0
    handle_end = handle_end or 0

    attrs = {
        "COMPN_GlobalStart": start - handle_start,
        "COMPN_GlobalEnd": end + handle_end
    }

    # set frame range
    if set_render_range:
        attrs.update({
            "COMPN_RenderStart": start,
            "COMPN_RenderEnd": end
        })

    with comp_lock_and_undo_chunk(comp):
        comp.SetAttrs(attrs)


def set_asset_framerange(asset_doc=None):
    """Set Comp's frame range based on current asset"""
    if asset_doc is None:
        asset_doc = get_current_project_asset()

    start = asset_doc["data"]["frameStart"]
    end = asset_doc["data"]["frameEnd"]
    handle_start = asset_doc["data"]["handleStart"]
    handle_end = asset_doc["data"]["handleEnd"]
    update_frame_range(start, end, set_render_range=True,
                       handle_start=handle_start,
                       handle_end=handle_end)


def set_asset_fps(asset_doc=None):
    """Set Comp's frame rate (FPS) to based on current asset"""
    if asset_doc is None:
        asset_doc = get_current_project_asset()

    fps = float(asset_doc["data"].get("fps", 24.0))
    comp = get_current_comp()
    comp.SetPrefs({
        "Comp.FrameFormat.Rate": fps,
    })


def set_asset_resolution(asset_doc=None):
    """Set Comp's resolution width x height default based on current asset"""
    if asset_doc is None:
        asset_doc = get_current_project_asset()

    width = asset_doc["data"]["resolutionWidth"]
    height = asset_doc["data"]["resolutionHeight"]
    comp = get_current_comp()

    print("Setting comp frame format resolution to {}x{}".format(width,
                                                                 height))
    comp.SetPrefs({
        "Comp.FrameFormat.Width": width,
        "Comp.FrameFormat.Height": height,
    })


def validate_comp_prefs(comp=None, force_repair=False):
    """Validate current comp defaults with asset settings.

    Validates fps, resolutionWidth, resolutionHeight, aspectRatio.

    This does *not* validate frameStart, frameEnd, handleStart and handleEnd.
    """

    if comp is None:
        comp = get_current_comp()

    log = Logger.get_logger("validate_comp_prefs")

    fields = [
        "name",
        "data.fps",
        "data.resolutionWidth",
        "data.resolutionHeight",
        "data.pixelAspect"
    ]
    asset_doc = get_current_project_asset(fields=fields)
    asset_data = asset_doc["data"]

    comp_frame_format_prefs = comp.GetPrefs("Comp.FrameFormat")

    # Pixel aspect ratio in Fusion is set as AspectX and AspectY so we convert
    # the data to something that is more sensible to Fusion
    asset_data["pixelAspectX"] = asset_data.pop("pixelAspect")
    asset_data["pixelAspectY"] = 1.0

    validations = [
        ("fps", "Rate", "FPS"),
        ("resolutionWidth", "Width", "Resolution Width"),
        ("resolutionHeight", "Height", "Resolution Height"),
        ("pixelAspectX", "AspectX", "Pixel Aspect Ratio X"),
        ("pixelAspectY", "AspectY", "Pixel Aspect Ratio Y")
    ]

    invalid = []
    for key, comp_key, label in validations:
        asset_value = asset_data[key]
        comp_value = comp_frame_format_prefs.get(comp_key)
        if asset_value != comp_value:
            invalid_msg = "{} {} should be {}".format(label,
                                                      comp_value,
                                                      asset_value)
            invalid.append(invalid_msg)

            if not force_repair:
                # Do not log warning if we force repair anyway
                log.warning(
                    "Comp {pref} {value} does not match asset "
                    "'{asset_name}' {pref} {asset_value}".format(
                        pref=label,
                        value=comp_value,
                        asset_name=asset_doc["name"],
                        asset_value=asset_value)
                )

    if invalid:

        def _on_repair():
            attributes = dict()
            for key, comp_key, _label in validations:
                value = asset_data[key]
                comp_key_full = "Comp.FrameFormat.{}".format(comp_key)
                attributes[comp_key_full] = value
            comp.SetPrefs(attributes)

        if force_repair:
            log.info("Applying default Comp preferences..")
            _on_repair()
            return

        from . import menu
        from openpype.widgets import popup
        from openpype.style import load_stylesheet
        dialog = popup.Popup(parent=menu.menu)
        dialog.setWindowTitle("Fusion comp has invalid configuration")

        msg = "Comp preferences mismatches '{}'".format(asset_doc["name"])
        msg += "\n" + "\n".join(invalid)
        dialog.setMessage(msg)
        dialog.setButtonText("Repair")
        dialog.on_clicked.connect(_on_repair)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        dialog.setStyleSheet(load_stylesheet())


@contextlib.contextmanager
def maintained_selection(comp=None):
    """Reset comp selection from before the context after the context"""
    if comp is None:
        comp = get_current_comp()

    previous_selection = comp.GetToolList(True).values()
    try:
        yield
    finally:
        flow = comp.CurrentFrame.FlowView
        flow.Select()  # No args equals clearing selection
        if previous_selection:
            for tool in previous_selection:
                flow.Select(tool, True)


@contextlib.contextmanager
def maintained_comp_range(comp=None,
                          global_start=True,
                          global_end=True,
                          render_start=True,
                          render_end=True):
    """Reset comp frame ranges from before the context after the context"""
    if comp is None:
        comp = get_current_comp()

    comp_attrs = comp.GetAttrs()
    preserve_attrs = {}
    if global_start:
        preserve_attrs["COMPN_GlobalStart"] = comp_attrs["COMPN_GlobalStart"]
    if global_end:
        preserve_attrs["COMPN_GlobalEnd"] = comp_attrs["COMPN_GlobalEnd"]
    if render_start:
        preserve_attrs["COMPN_RenderStart"] = comp_attrs["COMPN_RenderStart"]
    if render_end:
        preserve_attrs["COMPN_RenderEnd"] = comp_attrs["COMPN_RenderEnd"]

    try:
        yield
    finally:
        comp.SetAttrs(preserve_attrs)


def get_frame_path(path):
    """Get filename for the Fusion Saver with padded number as '#'

    >>> get_frame_path("C:/test.exr")
    ('C:/test', 4, '.exr')

    >>> get_frame_path("filename.00.tif")
    ('filename.', 2, '.tif')

    >>> get_frame_path("foobar35.tif")
    ('foobar', 2, '.tif')

    Args:
        path (str): The path to render to.

    Returns:
        tuple: head, padding, tail (extension)

    """
    filename, ext = os.path.splitext(path)

    # Find a final number group
    match = re.match('.*?([0-9]+)$', filename)
    if match:
        padding = len(match.group(1))
        # remove number from end since fusion
        # will swap it with the frame number
        filename = filename[:-padding]
    else:
        padding = 4  # default Fusion padding

    return filename, padding, ext


def get_fusion_module():
    """Get current Fusion instance"""
    fusion = getattr(sys.modules["__main__"], "fusion", None)
    return fusion


def get_bmd_library():
    """Get bmd library"""
    bmd = getattr(sys.modules["__main__"], "bmd", None)
    return bmd


def get_current_comp():
    """Get current comp in this session"""
    fusion = get_fusion_module()
    if fusion is not None:
        comp = fusion.CurrentComp
        return comp


@contextlib.contextmanager
def comp_lock_and_undo_chunk(
    comp,
    undo_queue_name="Script CMD",
    keep_undo=True,
):
    """Lock comp and open an undo chunk during the context"""

    # If comp is already locked do nothing and consider us to
    # be inside another undo chunk currently. This allows nesting the chunks.
    if comp.IsLocked():
        yield
        return

    try:
        comp.Lock()
        comp.StartUndo(undo_queue_name)
        yield
    finally:
        comp.Unlock()
        comp.EndUndo(keep_undo)


def update_content_on_context_change():
    """Update all Creator instances to current asset"""
    host = registered_host()
    context = host.get_current_context()
    asset = context["asset_name"]
    task = context["task_name"]

    create_context = CreateContext(host, reset=True)

    for instance in create_context.instances:
        instance_asset = instance.get("asset")
        if instance_asset and instance_asset != asset:
            instance["asset"] = asset
        instance_task = instance.get("task")
        if instance_task and instance_task != task:
            instance["task"] = task

    create_context.save_changes()


def prompt_reset_context():
    """Prompt the user what context settings to reset.

    This prompt is used on saving to a different task to allow the scene to
    get matched to the new context.

    """
    # TODO: Cleanup this prototyped mess of imports and odd dialog
    # TODO: Reduce code duplication with the implementation in Maya+Houdini
    import openpype.tools.utils.widgets as widgets
    from qtpy import QtWidgets
    import qargparse  # noqa
    from openpype.style import load_stylesheet

    option_labels = {
        "fps": "FPS",
        "frame_range": "Frame Range",
        "resolution": "Comp Resolution",
        "instances": "Publish instances asset",
    }
    definitions = [
        qargparse.Boolean(key, label=label, default=True)
        for key, label in option_labels.items()
    ]

    dialog = widgets.OptionDialog()
    dialog.setWindowFlags(
        dialog.windowFlags() | QtCore.Qt.WindowStaysOnTopHint
    )
    dialog.create(definitions)
    dialog.setWindowTitle("Saving to different context. Reset options")
    dialog.setStyleSheet(load_stylesheet())

    # Insert descriptive label into the pup-up
    label = QtWidgets.QLabel("You are saving your scene into a different task."
                             "\n\n"
                             "Would you like to reset some settings for the "
                             "for the new context?\n")
    dialog.layout().insertWidget(0, label)

    if not dialog.exec_():
        return None

    options = dialog.parse()
    asset_doc = get_current_project_asset()
    if options.get("frame_range", True):
        set_asset_framerange(asset_doc)

    if options.get("fps", True):
        set_asset_fps(asset_doc)

    if options.get("resolution", True):
        set_asset_resolution(asset_doc)

    if options.get("instances", True):
        update_content_on_context_change()
