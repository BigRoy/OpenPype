from collections import defaultdict
import os
import logging

import six

import alembic.Abc

import pyblish.api
import openpype.api
import openpype.action
from openpype.client import (
    get_last_version_by_subset_name,
    get_representation_by_name
)
from openpype.pipeline import get_representation_path

import openpype.hosts.maya.api.action
from openpype.hosts.maya.api.lib import get_id, set_id


log = logging.getLogger(__name__)


def get_alembic_paths_by_property(filename, attr, verbose=False):
    # type: (str, str, bool) -> dict
    """Return attribute value per objects in the Alembic file.

    Reads an Alembic archive hierarchy and retrieves the
    value from the `attr` properties on the objects.

    Args:
        filename (str): Full path to Alembic archive to read.
        attr (str): Id attribute.
        verbose (bool): Whether to verbosely log missing attributes.

    Returns:
        dict: Mapping of node full path with its id

    """
    # Normalize alembic path
    filename = os.path.normpath(filename)
    filename = filename.replace("\\", "/")
    filename = str(filename)  # path must be string

    try:
        archive = alembic.Abc.IArchive(filename)
    except RuntimeError:
        # invalid alembic file - probably vrmesh
        log.warning("{} is not an alembic file".format(filename))
        return {}
    root = archive.getTop()

    iterator = list(root.children)
    obj_ids = {}

    for obj in iterator:
        name = obj.getFullName()

        # include children for coming iterations
        iterator.extend(obj.children)

        props = obj.getProperties()
        if props.getNumProperties() == 0:
            # Skip those without properties, e.g. '/materials' in a gpuCache
            continue

        # THe custom attribute is under the properties' first container under
        # the ".arbGeomParams"
        prop = props.getProperty(0)  # get base property

        _property = None
        try:
            geo_params = prop.getProperty('.arbGeomParams')
            _property = geo_params.getProperty(attr)
        except KeyError:
            if verbose:
                log.debug("Missing attr on: {0}".format(name))
            continue

        if not _property.isConstant():
            log.warning("Id not constant on: {0}".format(name))

        # Get first value sample
        value = _property.getValue()[0]

        obj_ids[name] = value

    return obj_ids


def get_alembic_ids_cache(path):
    # type: (str) -> dict
    """Build a id to node mapping in Alembic file.

    Nodes without IDs are ignored.

    Returns:
        dict: Mapping of id to nodes in the Alembic.

    """
    node_ids = get_alembic_paths_by_property(path, attr="cbId")
    id_nodes = defaultdict(list)
    for node, _id in six.iteritems(node_ids):
        id_nodes[_id].append(node)

    return dict(six.iteritems(id_nodes))


class ValidateModelIdsToExistingVersion(pyblish.api.InstancePlugin):
    """Validate node ids haven't changed since latest published version.

    The node ids of the current workfile are compared to the latest published
    Alembic of the subset. For nodes names that are found in the previous
    publish it compares whether the `cbId` attribute remained the same value.
    If the attribute has changed then it's considered invalid.

    """

    order = openpype.api.ValidateContentsOrder
    hosts = ["maya"]
    families = ["model"]
    label = "Model ids match latest version"
    actions = [openpype.hosts.maya.api.action.SelectInvalidAction,
               openpype.action.RepairAction]

    optional = True
    log_changed_hierarchies = True

    def process(self, instance):

        invalid = self.get_invalid(instance)
        if invalid:
            raise RuntimeError("Detected changed ids "
                               "on {} nodes".format(len(invalid)))

    @classmethod
    def get_invalid(cls, instance):

        invalid = []
        for node, previous_id, current_id in cls.iter_mismatches(instance):
            # Checked alembic node id does not match what's currently
            # in our scene. We can now assume our workfiles id has
            # changed since a previous publish.
            cls.log.error("Id changed for: {}\n"
                          "\t{} (old)\n"
                          "\t{} (new)".format(node, previous_id, current_id))
            invalid.append(node)

        return invalid

    @classmethod
    def repair(cls, instance):
        for node, previous_id, _ in cls.iter_mismatches(instance):
            cls.log.info("Updating id for {}: {}".format(node, previous_id))
            set_id(node, previous_id, overwrite=True)

    @classmethod
    def iter_mismatches(cls, instance):
        """Yield node, previous_id, new_id upon differing ids"""

        project_name = instance.context.data["projectName"]
        asset_doc = instance.data["assetEntity"]
        subset_name = instance.data["subset"]
        version = get_last_version_by_subset_name(project_name,
                                                  subset_name=subset_name,
                                                  asset_id=asset_doc["_id"])
        if not version:
            cls.log.debug("Subset does not exist yet: {}".format(subset_name))
            return

        representation = get_representation_by_name(project_name,
                                                    "abc",
                                                    version_id=version["_id"])
        if not representation:
            return

        cls.log.info("Validating using '{}' version v{:03d}".format(
            subset_name,
            version["name"]
        ))

        path = get_representation_path(representation)
        if not path or not os.path.exists(path):
            cls.log.warning("Representation path does not exist: "
                            "{}".format(path))
            return

        # Alembic paths by id
        ids_to_paths = get_alembic_ids_cache(path)
        abc_path_to_id = {
            path: _id
            for _id, paths in ids_to_paths.items()
            for path in paths
        }

        # Get instance node by the abc equivalent path
        instance_nodes_id_by_abc_path = dict()
        for node in instance:

            # Consider only nodes with ids
            node_id = get_id(node)
            if not node_id:
                continue

            # TODO: Strip parent hierarchy if includeParentHierarchy is False
            abc_equivalent_path = node.replace("|", "/")

            instance_nodes_id_by_abc_path[abc_equivalent_path] = (
                node, get_id(node)
            )

        if cls.log_changed_hierarchies:
            # Log warning for any removed paths that previously had ids
            for path in abc_path_to_id.keys():
                if path not in instance_nodes_id_by_abc_path:
                    cls.log.warning("Detected removed path: {}".format(path))

            # Log warning for any added paths that previously didn't have an id
            for abc_path in sorted(instance_nodes_id_by_abc_path.keys()):
                if abc_path not in abc_path_to_id:
                    cls.log.warning("Detected new path: {}".format(abc_path))

        # Iterating over sorted provides more structured log messages
        for abc_path, (node, node_id) in sorted(
                instance_nodes_id_by_abc_path.items()):
            abc_node_id = abc_path_to_id.get(abc_path, None)
            if abc_node_id is not None:
                if abc_node_id != node_id:
                    yield node, abc_node_id, node_id
