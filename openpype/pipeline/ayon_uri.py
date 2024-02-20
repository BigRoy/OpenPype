import os
import copy
from urllib.parse import urlparse, parse_qs

from openpype.client import (
    get_asset_by_name,
    get_subset_by_name,
    get_representation_by_name,
    get_hero_version_by_subset_id,
    get_version_by_name,
    get_last_version_by_subset_id
)
from openpype.pipeline import (
    get_representation_path
)


def parse_ayon_uri(uri):
    """Parse ayon entity URI into individual components.

    URI specification:
        ayon+entity://{project}/{asset}?product={product}
            &version={version}
            &representation={representation}
    URI example:
        ayon+entity://test/hero?product=modelMain&version=2&representation=usd

    However - if the netloc is `ayon://` it will by default also resolve as
    `ayon+entity://` on AYON server, thus we need to support both. The shorter
    `ayon://` is preferred for user readability.

    Example:
    >>> parse_ayon_uri(
    >>>     "ayon://test/villain?product=modelMain&version=2&representation=usd"  # noqa: E501
    >>> )
    {'project': 'test', 'asset': 'villain',
     'product': 'modelMain', 'version': 1,
     'representation': 'usd'}
    >>> parse_ayon_uri(
    >>>     "ayon+entity://project/asset?product=renderMain&version=3&representation=exr"  # noqa: E501
    >>> )
    {'project': 'project', 'asset': 'asset',
     'product': 'renderMain', 'version': 3,
     'representation': 'exr'}

    Returns:
        dict[str, Union[str, int]]: The individual key with their values as
            found in the ayon entity URI.

    """

    if not (uri.startswith("ayon+entity://") or uri.startswith("ayon://")):
        return {}

    parsed = urlparse(uri)
    if parsed.scheme not in {"ayon+entity", "ayon"}:
        return {}

    result = {
        "project": parsed.netloc,
        "asset": parsed.path.strip("/")
    }
    query = parse_qs(parsed.query)
    for key in ["product", "version", "representation"]:
        if key in query:
            result[key] = query[key][0]

    # Convert version to integer if it is a digit
    version = result.get("version")
    if version is not None and version.isdigit():
        result["version"] = int(version)

    return result


def construct_ayon_uri(
        project_name,
        asset_name,
        product,
        version,
        representation_name
):
    """Construct Ayon entity URI from its components

    Returns:
        str: Ayon Entity URI to query entity path.
            Also works with `get_representation_path_by_ayon_uri`
    """
    if not (isinstance(version, int) or version in {"latest", "hero"}):
        raise ValueError(
            "Version must either be integer, 'latest' or 'hero'. "
            "Got: {}".format(version)
        )
    return (
        "ayon://{project}/{asset}?product={product}&version={version}"
        "&representation={representation}".format(
            project=project_name,
            asset=asset_name,
            product=product,
            version=version,
            representation=representation_name
        )
    )


def get_representation_by_names(
        project_name,
        asset_name,
        subset_name,
        version_name,
        representation_name,
):
    """Get representation entity for asset and subset.

    If version_name is "hero" then return the hero version
    If version_name is "latest" then return the latest version
    Otherwise use version_name as the exact integer version name.

    """

    if isinstance(asset_name, dict) and "name" in asset_name:
        # Allow explicitly passing asset document
        asset_doc = asset_name
    else:
        asset_doc = get_asset_by_name(project_name, asset_name, fields=["_id"])
    if not asset_doc:
        return

    if isinstance(subset_name, dict) and "name" in subset_name:
        # Allow explicitly passing subset document
        subset_doc = subset_name
    else:
        subset_doc = get_subset_by_name(project_name,
                                        subset_name,
                                        asset_id=asset_doc["_id"],
                                        fields=["_id"])
    if not subset_doc:
        return

    if version_name == "hero":
        version = get_hero_version_by_subset_id(project_name,
                                                subset_id=subset_doc["_id"])
    elif version_name == "latest":
        version = get_last_version_by_subset_id(project_name,
                                                subset_id=subset_doc["_id"])
    else:
        version = get_version_by_name(project_name,
                                      version_name,
                                      subset_id=subset_doc["_id"])
    if not version:
        return

    return get_representation_by_name(project_name,
                                      representation_name,
                                      version_id=version["_id"])


def get_representation_path_by_names(
        project_name,
        asset_name,
        subset_name,
        version_name,
        representation_name):
    """Get (latest) filepath for representation for asset and subset.

    See `get_representation_by_names` for more details.

    Returns:
        str: The representation path if the representation exists.

    """
    representation = get_representation_by_names(
        project_name,
        asset_name,
        subset_name,
        version_name,
        representation_name
    )
    if representation:
        path = get_representation_path(representation)
        return path.replace("\\", "/")


def get_representation_path_by_ayon_uri(
        uri,
        context=None
):
    """Return resolved path for Ayon entity URI.

    Allow resolving 'latest' paths from a publishing context's instances
    as if they will exist after publishing without them being integrated yet.

    Args:
        uri (str): Ayon entity URI. See `parse_ayon_uri`
        context (pyblish.api.Context): Publishing context.

    Returns:
        Union[str, None]: Returns the path if it could be resolved

    """
    query = parse_ayon_uri(uri)

    if context is not None and context.data["projectName"] == query["project"]:
        # Search first in publish context to allow resolving latest versions
        # from e.g. the current publish session if the context is provided
        if query["version"] == "hero":
            raise NotImplementedError(
                "Hero version resolving not implemented from context"
            )

        specific_version = isinstance(query["version"], int)
        for instance in context:
            if instance.data.get("asset") != query["asset"]:
                continue

            if instance.data.get("subset") != query["product"]:
                continue

            # Only consider if the instance has a representation by
            # that name
            representations = instance.data.get("representations", [])
            if not any(representation.get("name") == query["representation"]
                       for representation in representations):
                continue

            return get_instance_expected_output_path(
                instance,
                representation_name=query["representation"],
                version=query["version"] if specific_version else None
            )

    return get_representation_path_by_names(
        project_name=query["project"],
        asset_name=query["asset"],
        subset_name=query["product"],
        version_name=query["version"],
        representation_name=query["representation"],
    )


def get_instance_expected_output_path(instance, representation_name,
                                      ext=None, version=None):
    """Return expected publish filepath for representation in instance

    This does not validate whether the instance has any representation by the
    given name, extension and/or version.

    Arguments:
        instance (pyblish.api.Instance): publish instance
        representation_name (str): representation name
        ext (Optional[str]): extension for the file, useful if `name` += `ext`
        version (Optional[int]): if provided, force it to format to this
            particular version.
        representation_name (str): representation name

    Returns:
        str: Resolved path

    """

    if ext is None:
        ext = representation_name
    if version is None:
        version = instance.data["version"]

    context = instance.context
    anatomy = context.data["anatomy"]
    path_template_obj = anatomy.templates_obj["publish"]["path"]
    template_data = copy.deepcopy(instance.data["anatomyData"])
    template_data.update({
        "ext": ext,
        "representation": representation_name,
        "subset": instance.data["subset"],
        "asset": instance.data["asset"],
        "variant": instance.data.get("variant"),
        "version": version
    })

    template_filled = path_template_obj.format_strict(template_data)
    return os.path.normpath(template_filled)
