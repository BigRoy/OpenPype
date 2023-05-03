# -*- coding: utf-8 -*-
"""3dsmax specific Avalon/Pyblish plugin definitions."""
from pymxs import runtime as rt
from typing import Union
import six
from abc import ABCMeta
from openpype.pipeline import (
    CreatorError,
    Creator,
    CreatedInstance
)
from openpype.lib import BoolDef
from .lib import imprint, read, lsattr

MS_CUSTOM_ATTRIB = """attributes "openPypeData"
(
    parameters main rollout:OPparams
    (
        all_handles type:#maxObjectTab tabSize:0 tabSizeVariable:on
    )

    rollout OPparams "OP Parameters"
    (
        listbox list_node "Node References" items:#()
        button button_add "Add Selection"

        fn node_to_name the_node =
        (
            handle = the_node.handle
            obj_name = the_node.name
            handle_name = obj_name + "<" + handle as string + ">"
            return handle_name
        )

        on button_add pressed do
        (
            current_selection = selectByName title:"Select Objects To Add To
            Container" buttontext:"Add"
            temp_arr = #()
            i_node_arr = #()
            for c in current_selection do
            (
                handle_name = node_to_name c
                node_ref = NodeTransformMonitor node:c
                append temp_arr handle_name
                append i_node_arr node_ref
            )
            all_handles = i_node_arr
            list_node.items = temp_arr
        )

        on OPparams open do
        (
            if all_handles.count != 0 do
            (
                temp_arr = #()
                for x in all_handles do
                (
                    print(x.node)
                    handle_name = node_to_name x.node
                    append temp_arr handle_name
                )
                list_node.items = temp_arr
            )
        )
    )
)"""


class OpenPypeCreatorError(CreatorError):
    pass


class MaxCreatorBase(object):

    @staticmethod
    def cache_subsets(shared_data):
        if shared_data.get("max_cached_subsets") is None:
            shared_data["max_cached_subsets"] = {}
            cached_instances = lsattr("id", "pyblish.avalon.instance")
            for i in cached_instances:
                creator_id = rt.getUserProp(i, "creator_identifier")
                if creator_id not in shared_data["max_cached_subsets"]:
                    shared_data["max_cached_subsets"][creator_id] = [i.name]
                else:
                    shared_data[
                        "max_cached_subsets"][creator_id].append(
                        i.name)  # noqa
        return shared_data

    @staticmethod
    def create_instance_node(node):
        """Create instance node.

        If the supplied node is existing node, it will be used to hold the
        instance, otherwise new node of type Dummy will be created.

        Args:
            node (rt.MXSWrapperBase, str): Node or node name to use.

        Returns:
            instance
        """
        if isinstance(node, str):
            node = rt.container(name=node)

        attrs = rt.execute(MS_CUSTOM_ATTRIB)
        rt.custAttributes.add(node.baseObject, attrs)

        return node


@six.add_metaclass(ABCMeta)
class MaxCreator(Creator, MaxCreatorBase):
    selected_nodes = []

    def create(self, subset_name, instance_data, pre_create_data):
        if pre_create_data.get("use_selection"):
            self.selected_nodes = rt.getCurrentSelection()

        instance_node = self.create_instance_node(subset_name)
        instance_data["instance_node"] = instance_node.name
        instance = CreatedInstance(
            self.family,
            subset_name,
            instance_data,
            self
        )
        if pre_create_data.get("use_selection"):

            node_list = []
            for i in self.selected_nodes:
                node_ref = rt.NodeTransformMonitor(node=i)
                node_list.append(node_ref)

            # Setting the property
            rt.setProperty(
                instance_node.openPypeData, "all_handles", node_list)

        self._add_instance_to_context(instance)
        imprint(instance_node.name, instance.data_to_store())

        return instance

    def collect_instances(self):
        self.cache_subsets(self.collection_shared_data)
        for instance in self.collection_shared_data["max_cached_subsets"].get(self.identifier, []):  # noqa
            created_instance = CreatedInstance.from_existing(
                read(rt.GetNodeByName(instance)), self
            )
            self._add_instance_to_context(created_instance)

    def update_instances(self, update_list):
        for created_inst, changes in update_list:
            instance_node = created_inst.get("instance_node")

            new_values = {
                key: changes[key].new_value
                for key in changes.changed_keys
            }
            imprint(
                instance_node,
                new_values,
            )

    def remove_instances(self, instances):
        """Remove specified instance from the scene.

        This is only removing `id` parameter so instance is no longer
        instance, because it might contain valuable data for artist.

        """
        for instance in instances:
            if instance_node := rt.GetNodeByName(instance.data.get("instance_node")):  # noqa
                rt.Select(instance_node)
                rt.custAttributes.add(instance_node.baseObject, "openPypeData")
                rt.Delete(instance_node)

            self._remove_instance_from_context(instance)

    def get_pre_create_attr_defs(self):
        return [
            BoolDef("use_selection", label="Use selection")
        ]
