# -*- coding: utf-8 -*-
"""Simple alembic loader for 3dsmax.

Because of limited api, alembics can be only loaded, but not easily updated.

"""
import os
from openpype.pipeline import load, get_representation_path
from openpype.hosts.max.api import lib, maintained_selection
from openpype.hosts.max.api.lib import unique_namespace
from openpype.hosts.max.api.pipeline import (
    containerise,
    import_custom_attribute_data,
    update_custom_attribute_data
)


class AbcLoader(load.LoaderPlugin):
    """Alembic loader."""

    families = ["camera", "animation", "pointcache"]
    label = "Load Alembic"
    representations = ["abc"]
    order = -10
    icon = "code-fork"
    color = "orange"

    def load(self, context, name=None, namespace=None, data=None):
        from pymxs import runtime as rt

        file_path = self.filepath_from_context(context)
        file_path = os.path.normpath(file_path)

        abc_before = {
            c
            for c in rt.rootNode.Children
            if rt.classOf(c) == rt.AlembicContainer
        }

        rt.AlembicImport.ImportToRoot = False
        rt.importFile(file_path, rt.name("noPrompt"), using=rt.AlembicImport)

        abc_after = {
            c
            for c in rt.rootNode.Children
            if rt.classOf(c) == rt.AlembicContainer
        }

        # This should yield new AlembicContainer node
        abc_containers = abc_after.difference(abc_before)

        if len(abc_containers) != 1:
            self.log.error("Something failed when loading.")

        abc_container = abc_containers.pop()
        selections = rt.GetCurrentSelection()
        import_custom_attribute_data(
            abc_container, abc_container.Children)
        for abc in selections:
            for cam_shape in abc.Children:
                cam_shape.playbackType = 2

        namespace = unique_namespace(
            name + "_",
            suffix="_",
        )

        return containerise(
            name, [abc_container], context,
            namespace, loader=self.__class__.__name__
        )

    def update(self, container, representation):
        from pymxs import runtime as rt

        path = get_representation_path(representation)
        node = rt.GetNodeByName(container["instance_node"])

        nodes_list = []
        with maintained_selection():
            rt.Select(node.Children)

            for alembic in rt.Selection:
                abc = rt.GetNodeByName(alembic.name)
                update_custom_attribute_data(abc, abc.Children)
                rt.Select(abc.Children)
                for abc_con in rt.Selection:
                    abc_container = rt.GetNodeByName(abc_con.name)
                    abc_container.source = path
                    rt.Select(abc_container.Children)
                    for abc_obj in rt.Selection:
                        alembic_obj = rt.GetNodeByName(abc_obj.name)
                        alembic_obj.source = path
                        nodes_list.append(alembic_obj)

        lib.imprint(
            container["instance_node"],
            {"representation": str(representation["_id"])},
        )

    def switch(self, container, representation):
        self.update(container, representation)

    def remove(self, container):
        from pymxs import runtime as rt

        node = rt.GetNodeByName(container["instance_node"])
        rt.Delete(node)

    @staticmethod
    def get_container_children(parent, type_name):
        from pymxs import runtime as rt

        def list_children(node):
            children = []
            for c in node.Children:
                children.append(c)
                children += list_children(c)
            return children

        filtered = []
        for child in list_children(parent):
            class_type = str(rt.classOf(child.baseObject))
            if class_type == type_name:
                filtered.append(child)

        return filtered
