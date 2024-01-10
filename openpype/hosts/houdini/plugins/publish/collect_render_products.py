import re
import os

import hou
import pxr.UsdRender

import pyblish.api


class CollectRenderProducts(pyblish.api.InstancePlugin):
    """Collect USD Render Products.

    The render products are collected from the USD Render ROP node by detecting
    what the selected Render Settings prim path is, then finding those
    Render Settings in the USD Stage and collecting the targeted Render
    Products and their expected filenames.

    """

    label = "Collect Render Products"
    order = pyblish.api.CollectorOrder + 0.4
    hosts = ["houdini"]
    families = ["usdrender"]

    def process(self, instance):

        rop_node = hou.node(instance.data["instance_node"])
        node = instance.data.get("output_node")
        if not node:
            rop_path = rop_node.path()
            raise RuntimeError(
                "No output node found. Make sure to connect an "
                "input to the USD ROP: %s" % rop_path
            )

        override_output_image = rop_node.evalParm("outputimage")

        filenames = []
        files_by_product = {}
        stage = node.stage()
        for prim_path in self.get_render_products(rop_node, stage):
            prim = stage.GetPrimAtPath(prim_path)
            if not prim or not prim.IsA(pxr.UsdRender.Product):
                self.log.warning("Found invalid render product path "
                                 "configured in render settings that is not a "
                                 "Render Product prim: %s", prim_path)
                continue

            # Get Render Product Name
            if override_output_image:
                name = override_output_image
            else:
                # We force taking it from any random time sample as opposed to
                # "default" that the USD Api falls back to since that won't
                # return time sampled values if they were set per time sample.
                product = pxr.UsdRender.Product(prim)
                name = product.GetProductNameAttr().Get(time=0)

            dirname = os.path.dirname(name)
            basename = os.path.basename(name)

            dollarf_regex = r"(\$F([0-9]?))"
            frame_regex = r"^(.+\.)([0-9]+)(\.[a-zA-Z]+)$"
            if re.match(dollarf_regex, basename):
                # TODO: Confirm this actually is allowed USD stages and HUSK
                # Substitute $F
                def replace(match):
                    """Replace $F4 with padded #."""
                    padding = int(match.group(2)) if match.group(2) else 1
                    return "#" * padding

                filename_base = re.sub(dollarf_regex, replace, basename)
                filename = os.path.join(dirname, filename_base)
            else:
                # It may be the case that the current USD stage has stored
                # product name samples (e.g. when loading a USD file with
                # time samples) where it does not refer to e.g. $F4. And thus
                # it refers to the actual path like /path/to/frame.1001.exr
                # TODO: It would be better to maybe sample product name
                #  attribute `ValueMightBeTimeVarying` and if so get it per
                #  frame using `attr.Get(time=frame)` to ensure we get the
                #  actual product name set at that point in time?
                # Substitute basename.0001.ext
                def replace(match):
                    prefix, frame, ext = match.groups()
                    padding = "#" * len(frame)
                    return prefix + padding + ext

                filename_base = re.sub(frame_regex, replace, basename)
                filename = os.path.join(dirname, filename_base)
                filename = filename.replace("\\", "/")

            assert "#" in filename, (
                "Couldn't resolve render product name "
                "with frame number: %s" % name
            )

            filenames.append(filename)

            # TODO: Support multiple render products (currently this product
            #   is assumed to be the beauty product or multilayer product)
            #     files_by_product[aov_name] = self.generate_expected_files(
            files_by_product[""] = self.generate_expected_files(
                instance,
                filename
            )
            self.log.info("Collected %s name: %s", prim_path, filename)

        # Filenames for Deadline
        instance.data["files"] = filenames
        instance.data.setdefault("expectedFiles", []).append(files_by_product)

    def get_render_products(self, usdrender_rop, stage):
        """"The render products in the defined render settings

        Args:
            usdrender_rop (hou.Node): The Houdini USD Render ROP node.
            stage (pxr.Usd.Stage): The USD stage to find the render settings
                 in. This is usually the stage from the LOP path the USD Render
                 ROP node refers to.

        Returns:
            List[Sdf.Path]: Render Product paths enabled in the render settings

        """
        path = usdrender_rop.evalParm("rendersettings")
        if not path:
            path = "/Render/rendersettings"

        prim = stage.GetPrimAtPath(path)
        if not prim:
            self.log.warning("No render settings primitive found at: %s", path)
            return []

        render_settings = pxr.UsdRender.Settings(prim)
        if not render_settings:
            self.log.warning("Prim at %s is not a valid RenderSettings prim.",
                             path)
            return []

        return render_settings.GetProductsRel().GetTargets()

    def generate_expected_files(self, instance, path):
        """Generate full sequence of expected files from a filepath.

        The filepath should have '#' token as placeholder for frame numbers or
        should have %04d or %d placeholders. The `#` characters indicate frame
        number and padding, e.g. #### becomes 0001 for frame 1.

        Args:
            instance (pyblish.api.Instance): The publish instance.
            path (str): The filepath to generate the list of output files for.

        Returns:
            list: Filepath per frame.

        """

        folder = os.path.dirname(path)
        filename = os.path.basename(path)

        if "#" in filename:
            def replace(match):
                return "%0{}d".format(len(match.group()))

            filename = re.sub("#+", replace, filename)

        if "%" not in filename:
            # Not a sequence, single file
            return path

        expected_files = []
        start = instance.data["frameStartHandle"]
        end = instance.data["frameEndHandle"]

        for frame in range(int(start), (int(end) + 1)):
            expected_files.append(
                os.path.join(folder, (filename % frame)).replace("\\", "/"))

        return expected_files
