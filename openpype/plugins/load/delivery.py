import os
import copy
import platform
import re
from collections import defaultdict

import clique
from qtpy import QtWidgets, QtCore, QtGui

from openpype.client import get_representations, get_versions
from openpype.pipeline import load, Anatomy
from openpype import resources, style

from openpype.lib import (
    format_file_size,
    get_datetime_data,
)
from openpype.pipeline.load import get_representation_path_with_anatomy
from openpype.pipeline.delivery import (
    get_format_dict,
    check_destination_path,
    deliver_single_file,
    deliver_sequence,
    format_delivery_path,
    # todo: avoid private access
    _copy_file,
)
from openpype.lib import StringTemplate


def assemble(files):
    """Returns collections (sequences) and separate files.

    Args:
        files(list): list of filepaths

    Returns:
        tuple[List[clique.Collection], List[str]]: 2-tuple of
            list of collections and list of files not part of a collection
    """

    patterns = [clique.PATTERNS["frames"]]
    collections, remainder = clique.assemble(
        files, minimum_items=1, patterns=patterns)
    return collections, remainder


class Delivery(load.SubsetLoaderPlugin):
    """Export selected versions to folder structure from Template"""

    is_multiple_contexts_compatible = True
    sequence_splitter = "__sequence_splitter__"

    representations = ["*"]
    families = ["*"]
    tool_names = ["library_loader"]

    label = "Deliver Versions"
    order = 35
    icon = "upload"
    color = "#d8d8d8"

    def message(self, text):
        msgBox = QtWidgets.QMessageBox()
        msgBox.setText(text)
        msgBox.setStyleSheet(style.load_stylesheet())
        msgBox.setWindowFlags(
            msgBox.windowFlags() | QtCore.Qt.FramelessWindowHint
        )
        msgBox.exec_()

    def load(self, contexts, name=None, namespace=None, options=None):
        try:
            dialog = DeliveryOptionsDialog(contexts, self.log)
            dialog.exec_()
        except Exception:
            self.log.error("Failed to deliver versions.", exc_info=True)


class DeliveryOptionsDialog(QtWidgets.QDialog):
    """Dialog to select template where to deliver selected representations."""

    def __init__(self, contexts, log=None, parent=None):
        super(DeliveryOptionsDialog, self).__init__(parent=parent)

        self.setWindowTitle("OpenPype - Deliver versions")
        icon = QtGui.QIcon(resources.get_openpype_icon_filepath())
        self.setWindowIcon(icon)

        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowMinimizeButtonHint
        )

        self.setStyleSheet(style.load_stylesheet())

        project_name = contexts[0]["project"]["name"]
        self.anatomy = Anatomy(project_name)
        self._representations = None
        self.log = log
        self.currently_uploaded = 0

        self._project_name = project_name
        self._set_representations(project_name, contexts)

        dropdown = QtWidgets.QComboBox()
        self.templates = self._get_templates(self.anatomy)
        for name, _ in self.templates.items():
            dropdown.addItem(name)
        if self.templates and platform.system() == "Darwin":
            # fix macos QCombobox Style
            dropdown.setItemDelegate(QtWidgets.QStyledItemDelegate())
            # update combo box length to longest entry
            longest_key = max(self.templates.keys(), key=len)
            dropdown.setMinimumContentsLength(len(longest_key))

        template_label = QtWidgets.QLabel()
        template_label.setCursor(QtGui.QCursor(QtCore.Qt.IBeamCursor))
        template_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        renumber_frame = QtWidgets.QCheckBox()
        renumber_frame.setToolTip(
            "Renumber sequences instead of keeping their original frame start "
            "and end"
        )
        write_changelog = QtWidgets.QCheckBox()
        write_changelog.setChecked(True)
        write_changelog.setToolTip(
            "Write a CHANGELOG.html in delivery root folder. If the file "
            "already exists it will be prepended into the file."
        )

        first_frame_start = QtWidgets.QSpinBox()
        max_int = (1 << 32) // 2
        first_frame_start.setRange(0, max_int - 1)

        root_line_edit = QtWidgets.QLineEdit()
        root_line_edit.setToolTip(
            "Directory path where to place the delivered files."
        )

        repre_checkboxes_layout = QtWidgets.QFormLayout()
        repre_checkboxes_layout.setContentsMargins(10, 5, 5, 10)

        self._representation_checkboxes = {}
        for repre in self._get_representation_names():
            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(False)
            self._representation_checkboxes[repre] = checkbox

            checkbox.stateChanged.connect(self._update_selected_label)
            repre_checkboxes_layout.addRow(repre, checkbox)

        selected_label = QtWidgets.QLabel()

        input_widget = QtWidgets.QWidget(self)
        input_layout = QtWidgets.QFormLayout(input_widget)
        input_layout.setContentsMargins(10, 15, 5, 5)

        input_layout.addRow("Selected representations", selected_label)
        input_layout.addRow("Delivery template", dropdown)
        input_layout.addRow("Template value", template_label)
        input_layout.addRow("Renumber Frame", renumber_frame)
        input_layout.addRow("Renumber start frame", first_frame_start)
        input_layout.addRow("Root", root_line_edit)
        input_layout.addRow("Write changelog", write_changelog)
        input_layout.addRow("Representations", repre_checkboxes_layout)

        btn_delivery = QtWidgets.QPushButton("Deliver")
        btn_delivery.setEnabled(False)

        progress_bar = QtWidgets.QProgressBar(self)
        progress_bar.setMinimum = 0
        progress_bar.setMaximum = 100
        progress_bar.setVisible(False)

        text_area = QtWidgets.QTextEdit()
        text_area.setReadOnly(True)
        text_area.setVisible(False)
        text_area.setMinimumHeight(100)

        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(input_widget)
        layout.addStretch(1)
        layout.addWidget(btn_delivery)
        layout.addWidget(progress_bar)
        layout.addWidget(text_area)

        self.selected_label = selected_label
        self.template_label = template_label
        self.dropdown = dropdown
        self.first_frame_start = first_frame_start
        self.renumber_frame = renumber_frame
        self.write_changelog = write_changelog
        self.root_line_edit = root_line_edit
        self.progress_bar = progress_bar
        self.text_area = text_area
        self.btn_delivery = btn_delivery

        # Reset delivery root to last used value
        settings = QtCore.QSettings("ayon", "Delivery")
        root = settings.value("lastRoot", "")
        if root:
            self.root_line_edit.setText(root)
        self._settings = settings

        self.files_selected, self.size_selected = \
            self._get_counts(self._get_selected_repres())

        self._update_selected_label()
        self._update_template_value()

        btn_delivery.clicked.connect(self.deliver)
        dropdown.currentIndexChanged.connect(self._update_template_value)

        if not self.dropdown.count():
            self.text_area.setVisible(True)
            error_message = (
                "No Delivery Templates found!\n"
                "Add Template in [project_anatomy/templates/delivery]"
            )
            self.text_area.setText(error_message)
            self.log.error(error_message.replace("\n", " "))

    def deliver(self):
        """Main method to loop through all selected representations"""
        self.progress_bar.setVisible(True)
        self.btn_delivery.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        report_items = defaultdict(list)

        selected_representation_names = self._get_selected_repres()
        representations = [
            repre for repre in self._representations
            if repre["name"] in selected_representation_names
        ]

        delivery_root = self.root_line_edit.text()

        # Save delivery root setting for future runs
        self._settings.setValue("lastRoot", delivery_root)

        datetime_data = get_datetime_data()
        template_name = self.dropdown.currentText()
        format_dict = get_format_dict(self.anatomy, delivery_root)
        renumber_frame = self.renumber_frame.isChecked()
        frame_offset = self.first_frame_start.value()
        processed = set()
        for repre in representations:
            repre_path = get_representation_path_with_anatomy(
                repre, self.anatomy
            )
            repre_path = os.path.normpath(repre_path)

            anatomy_data = copy.deepcopy(repre["context"])
            new_report_items = check_destination_path(str(repre["_id"]),
                                                      self.anatomy,
                                                      anatomy_data,
                                                      datetime_data,
                                                      template_name)

            report_items.update(new_report_items)
            if new_report_items:
                continue

            args = [
                repre_path,
                repre,
                self.anatomy,
                template_name,
                anatomy_data,
                format_dict,
                report_items,
                self.log
            ]

            if repre.get("files"):
                src_paths = []
                for repre_file in repre["files"]:
                    src_path = self.anatomy.fill_root(repre_file["path"])
                    src_path = os.path.normpath(src_path)
                    src_paths.append(src_path)

                collections, remainder = assemble(src_paths)

                # We must consider a few different types of files, the `files`
                # list will include the representations files but also the
                # resource files (e.g. textures in published looks). So we
                # should identify initially whether the file we're processing
                # is a file of the representation or resource files.
                def deliver(*args):
                    new_report_items, uploaded = deliver_single_file(*args)
                    report_items.update(new_report_items)
                    self._update_progress(uploaded)

                def is_main_file(path):
                    """Return whether Collection or Path is main
                    representation file or sequence - if not it's a resource"""
                    if isinstance(path, clique.Collection):
                        return path.match(repre_path)
                    else:
                        return path == repre_path

                # Transfer source collection to destination collection
                resources = []
                for collection in collections:
                    if not is_main_file(collection):
                        resources.extend(list(collection))
                        continue

                    first_frame = min(collection.indexes)
                    for src_path, frame in zip(collection, collection.indexes):

                        # Renumber frames
                        if renumber_frame and first_frame != frame_offset:
                            # Calculate offset between
                            # first frame and current frame
                            # - '0' for first frame
                            offset = frame_offset - int(first_frame)

                            # Add offset to new frame start
                            dst_frame = int(frame) + offset
                            if dst_frame < 0:
                                msg = "Renumbered frame is below zero."
                                report_items[msg].append(src_path)
                                self.log.warning("{} <{}>".format(
                                    msg, dst_frame))
                                continue
                            frame = dst_frame

                        # Deliver main representation sequence frame
                        args[0] = src_path
                        anatomy_data["frame"] = frame
                        deliver(*args)

                for single_filepath in remainder:
                    if not is_main_file(single_filepath):
                        resources.append(single_filepath)
                        continue

                    # Deliver main representation file
                    args[0] = single_filepath
                    deliver(*args)

                # Resource files will be transferred to the last folder
                # defined by the delivery template without renaming
                # the files but keeping any subfolders from the source
                # file compared to the representations 'template' publish/
                # folder
                if not resources:
                    continue

                publish_dir_template = (
                    os.path.dirname(repre["data"]["template"])
                )
                publish_dir = StringTemplate.format_template(
                    publish_dir_template, repre["context"]
                )
                delivery_dir = os.path.dirname(format_delivery_path(
                    anatomy=self.anatomy,
                    template_name=template_name,
                    anatomy_data=anatomy_data,
                    format_dict=format_dict
                ))
                for resource in resources:
                    # Deliver resource file
                    relative_path = os.path.relpath(resource, publish_dir)
                    destination = os.path.join(delivery_dir, relative_path)
                    if destination in processed:
                        # Resources can be attached to more than one
                        # representation so we might end up trying to process
                        # the path more than once, if so we ignore it
                        continue

                    destination_dir = os.path.dirname(destination)
                    os.makedirs(destination_dir, exist_ok=True)
                    _copy_file(resource, destination)
                    self._update_progress(1)
                    processed.add(destination)

            else:  # fallback for Pype2 and representations without files
                frame = repre['context'].get('frame')
                if frame:
                    repre["context"]["frame"] = len(str(frame)) * "#"

                if not frame:
                    new_report_items, uploaded = deliver_single_file(*args)
                else:
                    new_report_items, uploaded = deliver_sequence(*args)
                report_items.update(new_report_items)
                self._update_progress(uploaded)

        report_text = self._format_report(report_items)
        if self.write_changelog.isChecked() and not report_items:
            # success - let's report what happened
            delivery_report = self._format_delivery_report(representations,
                                                           datetime_data)
            # Write delivery report file
            changelog_path = os.path.join(delivery_root, "CHANGELOG.html")
            SimpleHTML.prepend_body(changelog_path, delivery_report)
            report_text += f"Written to changelog: {changelog_path}"

        self.text_area.setText(report_text)
        self.text_area.setVisible(True)

    def _get_representation_names(self):
        """Get set of representation names for checkbox filtering."""
        return set([repre["name"] for repre in self._representations])

    def _get_templates(self, anatomy):
        """Adds list of delivery templates from Anatomy to dropdown."""
        templates = {}
        for template_name, value in anatomy.templates["delivery"].items():
            if not isinstance(value, str) or not value.startswith('{root'):
                continue

            templates[template_name] = value

        return templates

    def _set_representations(self, project_name, contexts):
        version_ids = [context["version"]["_id"] for context in contexts]

        repres = list(get_representations(
            project_name, version_ids=version_ids
        ))

        self._representations = repres

    def _get_counts(self, selected_repres=None):
        """Returns tuple of number of selected files and their size."""
        files_selected = 0
        size_selected = 0

        # Different representation can reference the same filepath due to
        # 'resource' transfers that get linked to each representation
        processed = set()
        for repre in self._representations:
            if repre["name"] in selected_repres:
                files = repre.get("files", [])
                if not files:  # for repre without files, cannot divide by 0
                    files_selected += 1
                    size_selected += 0
                else:
                    for repre_file in files:
                        path = repre_file["path"]
                        if path in processed:
                            continue

                        files_selected += 1
                        size_selected += repre_file["size"]
                        processed.add(path)

        return files_selected, size_selected

    def _prepare_label(self):
        """Provides text with no of selected files and their size."""
        label = "{} files, size {}".format(
            self.files_selected,
            format_file_size(self.size_selected))
        return label

    def _get_selected_repres(self):
        """Returns list of representation names filtered from checkboxes."""
        selected_repres = []
        for repre_name, chckbox in self._representation_checkboxes.items():
            if chckbox.isChecked():
                selected_repres.append(repre_name)

        return selected_repres

    def _update_selected_label(self):
        """Updates label with list of number of selected files."""
        selected_repres = self._get_selected_repres()
        self.files_selected, self.size_selected = \
            self._get_counts(selected_repres)
        self.selected_label.setText(self._prepare_label())
        # update delivery button state if any templates found
        if self.dropdown.count():
            self.btn_delivery.setEnabled(bool(selected_repres))

    def _update_template_value(self, _index=None):
        """Sets template value to label after selection in dropdown."""
        name = self.dropdown.currentText()
        template_value = self.templates.get(name)
        if template_value:
            self.template_label.setText(template_value)
            self.btn_delivery.setEnabled(bool(self._get_selected_repres()))

    def _update_progress(self, uploaded):
        """Update progress bar after each repre copied."""
        self.currently_uploaded += uploaded

        ratio = self.currently_uploaded / self.files_selected
        self.progress_bar.setValue(ratio * self.progress_bar.maximum())

    def _format_report(self, report_items):
        """Format final result and error details as html."""
        msg = "Delivery finished"
        if not report_items:
            msg += " successfully"
        else:
            msg += " with errors"
        txt = "<h2>{}</h2>".format(msg)
        for header, data in report_items.items():
            txt += "<h3>{}</h3>".format(header)
            for item in data:
                txt += "{}<br>".format(item)

        return txt

    def _format_delivery_report(self, representations, datetime_data):
        """Generate a simple HTML report.

        Roughly the report is:
            Delivered {datetime}
              path/to/version1   comment1
              path/to/version2   comment2

        Args:
            representations (list): The representations that got delivered
            datetime_data (dict): The datetime data of current delivery

        Returns:
            str: The HTML report

        """

        def sort_by_asset_and_subset(repre):
            context = repre["context"]
            return context["asset"], context["subset"]

        # Add an overview of the published versions with their
        # comments
        repre_by_version_id = defaultdict(list)
        for repre in sorted(representations, key=sort_by_asset_and_subset):
            repre_by_version_id[repre["parent"]].append(repre)

        versions_by_id = {
            version["_id"]: version for version in
            get_versions(
                project_name=self._project_name,
                version_ids=repre_by_version_id.keys(),
                fields=["_id", "data.comment"]
            )
        }

        header = (
            "<h3>Delivered {dd}-{mm}-{yyyy} {HH}:{MM}</h3>\n".format(
                **datetime_data
            )
        )

        context_label_template = (
            "{context[asset]}/{context[subset]}/v{context[version]:03d}"
        )
        report = []
        for version_id, version_repres in repre_by_version_id.items():
            version = versions_by_id[version_id]
            comment = version.get("data", {}).get("comment") or ""
            context = version_repres[0]["context"]
            context_label = context_label_template.format(context=context)
            message = (
                f"<a href=\"file:./{context_label}\">"
                f"<b>{context_label}</b></a>"
            )
            if comment:
                message += f"  <i>{comment}</i>"
            report.append(message)

        return header + "<br>\n".join(report)


class SimpleHTML:
    """Write a very simple HTML report.

     Using `prepend_body` you can  prepend logs into the body of a html file
     if it already exists, otherwise it will create the new html file.

     Even if the file already exists the file will be written using the html
     structure defined on this class - it will only preserve whatever is
     between <body> and </body> tags of the original file.

     """
    html_start = """<!DOCTYPE html>
<html>
<head>
    <title>CHANGELOG</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
html{box-sizing:border-box}*,*:before,*:after{box-sizing:inherit}
html{-ms-text-size-adjust:100%;-webkit-text-size-adjust:100%}
a{background-color:transparent}a:active,a:hover{outline-width:0}
b,strong{font-weight:bolder}
html,body{font-family:Verdana,sans-serif;font-size:15px;line-height:1.5}
html{overflow-x:hidden}
h1{font-size:36px}
h2{font-size:30px}
h3{font-size:24px}
h4{font-size:20px}
h5{font-size:18px}
h6{font-size:16px}
h1,h2,h3,h4,h5,h6{font-family:"SegoeUI",Arial,sans-serif;font-weight:400;margin:10px0}
body{margin:16px;}
h3{font-size:1.4em;margin-bottom:0px;margin-top:25px;color:#eb9b23;}
a{padding-left:10px;padding-right:20px;color:inherit}
    </style>
</head>
<body>
"""
    html_end = "</body>\n</html>"

    @classmethod
    def prepend_body(cls, filepath, content):

        # Get existing file content if it exists
        try:
            with open(filepath, "r") as f:
                existing_content = f.read()
        except FileNotFoundError as exc:
            existing_content = ""

        # Get body of existing content if there is any
        match = re.search("<body>(.*)</body>",
                          existing_content,
                          flags=re.DOTALL)
        existing_body = match.group(1) if match else ""

        # Define new body
        new_body = content + existing_body
        new_content = "\n".join([cls.html_start, new_body, cls.html_end])

        # Write new file
        with open(filepath, "w") as f:
            f.write(new_content)
