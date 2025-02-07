import pyblish.api

from openpype.pipeline.publish import PublishValidationError


class ValidateVrayProxy(pyblish.api.InstancePlugin):

    order = pyblish.api.ValidatorOrder
    label = "VRay Proxy Settings"
    hosts = ["maya"]
    families = ["vrayproxy"]

    def process(self, instance):
        data = instance.data

        if not data["setMembers"]:
            raise PublishValidationError(
                "'%s' is empty! This is a bug" % instance.name
            )

        if data["animation"]:
            if data["frameEnd"] < data["frameStart"]:
                raise PublishValidationError(
                    "End frame is smaller than start frame"
                )

        if not data["vrmesh"] and not data["alembic"]:
            raise PublishValidationError(
                "Both vrmesh and alembic are off. Needs at least one to"
                " publish."
            )
