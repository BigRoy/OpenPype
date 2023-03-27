from maya import cmds, mel

import pyblish.api

from openpype.client import get_subset_by_name
from openpype.pipeline import legacy_io


class CollectReview(pyblish.api.InstancePlugin):
    """Collect Review data

    """

    order = pyblish.api.CollectorOrder + 0.3
    label = 'Collect Review Data'
    families = ["review"]
    legacy = True

    def process(self, instance):

        self.log.debug('instance: {}'.format(instance))

        task = legacy_io.Session["AVALON_TASK"]

        # Get panel.
        instance.data["panel"] = cmds.playblast(
            activeEditor=True
        ).split("|")[-1]

        # get cameras
        members = instance.data['setMembers']
        cameras = cmds.ls(members, long=True,
                          dag=True, cameras=True)
        self.log.debug('members: {}'.format(members))

        # validate required settings
        assert len(cameras) == 1, "Not a single camera found in extraction"
        camera = cameras[0]
        self.log.debug('camera: {}'.format(camera))

        objectset = instance.context.data['objectsets']

        reviewable_subset = None
        reviewable_subset = list(set(members) & set(objectset))
        if reviewable_subset:
            assert len(reviewable_subset) <= 1, "Multiple subsets for review"
            self.log.debug('subset for review: {}'.format(reviewable_subset))

            i = 0
            for inst in instance.context:

                self.log.debug('filtering {}'.format(inst))
                data = instance.context[i].data

                if inst.name != reviewable_subset[0]:
                    self.log.debug('subset name does not match {}'.format(
                        reviewable_subset[0]))
                    i += 1
                    continue

                if data.get('families'):
                    data['families'].append('review')
                else:
                    data['families'] = ['review']
                self.log.debug('adding review family to {}'.format(
                    reviewable_subset))
                data['review_camera'] = camera
                # data["publish"] = False
                data['frameStartFtrack'] = instance.data["frameStartHandle"]
                data['frameEndFtrack'] = instance.data["frameEndHandle"]
                data['frameStartHandle'] = instance.data["frameStartHandle"]
                data['frameEndHandle'] = instance.data["frameEndHandle"]
                data["frameStart"] = instance.data["frameStart"]
                data["frameEnd"] = instance.data["frameEnd"]
                data['handles'] = instance.data.get('handles', None)
                data['step'] = instance.data['step']
                data['fps'] = instance.data['fps']
                data['review_width'] = instance.data['review_width']
                data['review_height'] = instance.data['review_height']
                data["isolate"] = instance.data["isolate"]
                data["panZoom"] = instance.data.get("panZoom", False)
                data["panel"] = instance.data["panel"]
                cmds.setAttr(str(instance) + '.active', 1)
                self.log.debug('data {}'.format(instance.context[i].data))
                instance.context[i].data.update(data)
                instance.data['remove'] = True
                self.log.debug('isntance data {}'.format(instance.data))
        else:
            legacy_subset_name = task + 'Review'
            asset_doc = instance.context.data['assetEntity']
            project_name = legacy_io.active_project()
            subset_doc = get_subset_by_name(
                project_name,
                legacy_subset_name,
                asset_doc["_id"],
                fields=["_id"]
            )
            if subset_doc:
                self.log.debug("Existing subsets found, keep legacy name.")
                instance.data['subset'] = legacy_subset_name

            instance.data['review_camera'] = camera
            instance.data['frameStartFtrack'] = \
                instance.data["frameStartHandle"]
            instance.data['frameEndFtrack'] = \
                instance.data["frameEndHandle"]

            # make ftrack publishable
            instance.data["families"] = ['ftrack']

            cmds.setAttr(str(instance) + '.active', 1)

            # Collect audio
            playback_slider = mel.eval('$tmpVar=$gPlayBackSlider')
            audio_name = cmds.timeControl(playback_slider,
                                          query=True,
                                          sound=True)
            display_sounds = cmds.timeControl(
                playback_slider, query=True, displaySound=True
            )

            def get_audio_node_data(node):
                return {
                    "offset": cmds.getAttr("{}.offset".format(node)),
                    "filename": cmds.getAttr("{}.filename".format(node))
                }

            audio_data = []

            if audio_name:
                audio_data.append(get_audio_node_data(audio_name))

            elif display_sounds:
                start_frame = int(cmds.playbackOptions(query=True, min=True))
                end_frame = int(cmds.playbackOptions(query=True, max=True))

                for node in cmds.ls(type="audio"):
                    # Check if frame range and audio range intersections,
                    # for whether to include this audio node or not.
                    duration = cmds.getAttr("{}.duration".format(node))
                    start_audio = cmds.getAttr("{}.offset".format(node))
                    end_audio = start_audio + duration

                    if start_audio <= end_frame and end_audio > start_frame:
                        audio_data.append(get_audio_node_data(node))

            instance.data["audio"] = audio_data
