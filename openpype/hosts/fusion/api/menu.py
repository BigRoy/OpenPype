import sys

from Qt import QtWidgets, QtCore

from openpype.tools.utils import host_tools
from openpype.style import load_stylesheet
from openpype.lib import register_event_callback
from openpype.hosts.fusion.scripts import (
    set_rendermode,
    duplicate_with_inputs
)
from openpype.hosts.fusion.api.lib import (
    set_asset_framerange,
    set_asset_resolution
)
from openpype.pipeline import legacy_io

from .pulse import FusionPulse
from .pipeline import CompSessions

self = sys.modules[__name__]
self.menu = None


class Spacer(QtWidgets.QWidget):
    def __init__(self, height, *args, **kwargs):
        super(Spacer, self).__init__(*args, **kwargs)

        self.setFixedHeight(height)

        real_spacer = QtWidgets.QWidget(self)
        real_spacer.setObjectName("Spacer")
        real_spacer.setFixedHeight(height)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(real_spacer)

        self.setLayout(layout)


class OpenPypeMenu(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(OpenPypeMenu, self).__init__(*args, **kwargs)

        self.setObjectName("OpenPypeMenu")

        self.setWindowFlags(
            QtCore.Qt.Window
            | QtCore.Qt.CustomizeWindowHint
            | QtCore.Qt.WindowTitleHint
            | QtCore.Qt.WindowMinimizeButtonHint
            | QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowStaysOnTopHint
        )
        self.render_mode_widget = None
        self.setWindowTitle("OpenPype")

        asset_label = QtWidgets.QLabel("Context", self)
        asset_label.setStyleSheet("""QLabel {
            font-size: 14px;
            font-weight: 600;
            color: #5f9fb8;
        }""")
        asset_label.setAlignment(QtCore.Qt.AlignHCenter)

        workfiles_btn = QtWidgets.QPushButton("Workfiles...", self)
        create_btn = QtWidgets.QPushButton("Create...", self)
        publish_btn = QtWidgets.QPushButton("Publish...", self)
        load_btn = QtWidgets.QPushButton("Load...", self)
        manager_btn = QtWidgets.QPushButton("Manage...", self)
        libload_btn = QtWidgets.QPushButton("Library...", self)
        rendermode_btn = QtWidgets.QPushButton("Set render mode...", self)
        set_framerange_btn = QtWidgets.QPushButton("Set Frame Range", self)
        set_resolution_btn = QtWidgets.QPushButton("Set Resolution", self)
        duplicate_with_inputs_btn = QtWidgets.QPushButton(
            "Duplicate with input connections", self
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 10, 20)

        layout.addWidget(asset_label)

        layout.addWidget(Spacer(15, self))

        layout.addWidget(workfiles_btn)

        layout.addWidget(Spacer(15, self))

        layout.addWidget(create_btn)
        layout.addWidget(load_btn)
        layout.addWidget(publish_btn)
        layout.addWidget(manager_btn)

        layout.addWidget(Spacer(15, self))

        layout.addWidget(libload_btn)

        layout.addWidget(Spacer(15, self))

        layout.addWidget(set_framerange_btn)
        layout.addWidget(set_resolution_btn)
        layout.addWidget(rendermode_btn)

        layout.addWidget(Spacer(15, self))

        layout.addWidget(duplicate_with_inputs_btn)

        self.setLayout(layout)

        # Store reference so we can update the label
        self.asset_label = asset_label

        workfiles_btn.clicked.connect(self.on_workfile_clicked)
        create_btn.clicked.connect(self.on_create_clicked)
        publish_btn.clicked.connect(self.on_publish_clicked)
        load_btn.clicked.connect(self.on_load_clicked)
        manager_btn.clicked.connect(self.on_manager_clicked)
        libload_btn.clicked.connect(self.on_libload_clicked)
        rendermode_btn.clicked.connect(self.on_rendermode_clicked)
        duplicate_with_inputs_btn.clicked.connect(
            self.on_duplicate_with_inputs_clicked)
        set_resolution_btn.clicked.connect(self.on_set_resolution_clicked)
        set_framerange_btn.clicked.connect(self.on_set_framerange_clicked)

        self._callbacks = []
        self.register_callback("taskChanged", self.on_task_changed)
        self.on_task_changed()

        # Force close current process if Fusion is closed
        self._pulse = FusionPulse(parent=self)
        self._pulse.start()

        self._check_active_comp_timer = QtCore.QTimer()
        self._check_active_comp_timer.setInterval(2500)
        self._check_active_comp_timer.start()
        self._check_active_comp_timer.timeout.connect(self._check_active_comp)

        self._fusion = getattr(sys.modules["__main__"], "fusion", None)
        self._last_comp = None

        # We directly check for current session comp because the OpenPype
        # menu could have been closed and re-opened by the user. By checking
        # directly the re-opened menu can directly enter the correct session
        # since by default it'd inherit the original session Fusion started in.
        self._check_active_comp()

    def _check_active_comp(self):
        """Check current comp against registered comp session for this fusion.

        If the current comp is not the same comp as in the last check then
        it will check if that comp id was found in this fusion process before
        with a valid OpenPype Session and update the current session to match
        the session that belonged to that comp. It allows to OpenPype menu
        to auto-match the correct context environment.

        """
        # TODO: Auto-updating on comp switch can be dangerous during publishing
        #       Investigate.
        comp = self._fusion.CurrentComp

        # Direct object comparison doesn't work with Fusion python objects
        if str(self._last_comp) == str(comp):
            return

        self._last_comp = comp
        sessions = CompSessions.instance()
        session = sessions.get_comp_session(comp)
        if session:
            if sessions.apply_comp_session(session):
                comp.Print("Automatic updating the active session "
                           "to new comp: {project} > {asset} > {task}".format(
                                project=session["AVALON_PROJECT"],
                                asset=session["AVALON_ASSET"],
                                task=session["AVALON_TASK"]))

    def on_task_changed(self):
        # Update current context label
        label = legacy_io.Session["AVALON_ASSET"]
        self.asset_label.setText(label)

    def register_callback(self, name, fn):

        # Create a wrapper callback that we only store
        # for as long as we want it to persist as callback
        def _callback(*args):
            fn()

        self._callbacks.append(_callback)
        register_event_callback(name, _callback)

    def deregister_all_callbacks(self):
        self._callbacks[:] = []

    def on_workfile_clicked(self):
        print("Clicked Workfile")
        host_tools.show_workfiles()

    def on_create_clicked(self):
        print("Clicked Create")
        host_tools.show_creator()

    def on_publish_clicked(self):
        print("Clicked Publish")
        host_tools.show_publish()

    def on_load_clicked(self):
        print("Clicked Load")
        host_tools.show_loader(use_context=True)

    def on_manager_clicked(self):
        print("Clicked Manager")
        host_tools.show_scene_inventory()

    def on_libload_clicked(self):
        print("Clicked Library")
        host_tools.show_library_loader()

    def on_rendermode_clicked(self):
        print("Clicked Set Render Mode")
        if self.render_mode_widget is None:
            window = set_rendermode.SetRenderMode()
            window.setStyleSheet(load_stylesheet())
            window.show()
            self.render_mode_widget = window
        else:
            self.render_mode_widget.show()

    def on_duplicate_with_inputs_clicked(self):
        print("Clicked Duplicate with input connections")
        duplicate_with_inputs.duplicate_with_input_connections()

    def on_set_resolution_clicked(self):
        print("Clicked Reset Resolution")
        set_asset_resolution()

    def on_set_framerange_clicked(self):
        print("Clicked Reset Framerange")
        set_asset_framerange()


def launch_openpype_menu():
    app = QtWidgets.QApplication(sys.argv)

    pype_menu = OpenPypeMenu()

    stylesheet = load_stylesheet()
    pype_menu.setStyleSheet(stylesheet)

    pype_menu.show()
    self.menu = pype_menu

    result = app.exec_()
    print("Shutting down..")
    sys.exit(result)
