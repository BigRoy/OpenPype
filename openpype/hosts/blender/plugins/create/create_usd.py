"""Create a USD Export."""

from openpype.hosts.blender.api import plugin, lib


class CreateUSD(plugin.BaseCreator):
    """Create USD Export"""

    identifier = "io.openpype.creators.blender.usd"
    name = "usdMain"
    label = "USD"
    family = "usd"
    icon = "gears"

    def create(
        self, subset_name: str, instance_data: dict, pre_create_data: dict
    ):
        # Run parent create method
        collection = super().create(
            subset_name, instance_data, pre_create_data
        )

        if pre_create_data.get("use_selection"):
            objects = lib.get_selection()
            for obj in objects:
                collection.objects.link(obj)
                if obj.type == 'EMPTY':
                    objects.extend(obj.children)

        return collection
