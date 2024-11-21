from __future__ import annotations
from collections import Counter
from typing import Annotated, Any, Sequence

from pydantic import AfterValidator, Field, field_validator

from ome_zarr_models.base import Base
from ome_zarr_models.utils import _unique_items_validator, duplicates
from ome_zarr_models.v04.axes import Axis, AxisType
from ome_zarr_models.v04.coordinate_transformations import (
    PathScale,
    PathTranslation,
    VectorScale,
    VectorTranslation,
)
from ome_zarr_models.v04.omero import Omero
from pydantic_zarr.v2 import ArraySpec, GroupSpec
import zarr

VALID_NDIM = (2, 3, 4, 5)
NUM_TX_MAX = 2


def ensure_transform_dimensionality(
    transforms: tuple[VectorScale | PathScale] | tuple[VectorScale | PathScale, VectorTranslation | PathTranslation],
) -> tuple[VectorScale | PathScale] | tuple[VectorScale | PathScale, VectorTranslation | PathTranslation]:
    """
    Ensures that the elements in the input sequence define transformations with identical dimensionality.
    """
    if isinstance(transforms[0], PathScale) or isinstance(transforms[1], PathTranslation):
        # it's not possible to check that the dimensionality of a path transform
        # is the same as the dimensionality of a vector transform
        return transforms
    
    ndims = tuple(tx.ndim for tx in transforms)
    ndims_set = set(ndims)
    if len(ndims_set) > 1:
        msg = (
            "The transforms have inconsistent dimensionality. "
            f"Got transforms with dimensionality = {ndims}."
        )
        raise ValueError(msg)
    return transforms

def ensure_scale_translation(
    transforms: tuple[VectorScale | PathScale] | tuple[VectorScale | PathScale, VectorTranslation | PathTranslation],
) -> tuple[VectorScale | PathScale] | tuple[VectorScale | PathScale, VectorTranslation | PathTranslation]:
    """
    Ensures that the first element is a scale transformation, the second element,
    if present, is a translation transform, and that there are only 1 or 2 transforms.
    """

    if len(transforms) == 0 or len(transforms) > 2:
        msg = f"Invalid number of transforms: got {len(transforms)}, expected 1 or 2"
        raise ValueError(msg)

    maybe_scale = transforms[0]
    if maybe_scale.type != "scale":
        msg = (
            "The first element of `coordinateTransformations` must be a scale "
            f"transform. Got {maybe_scale} instead."
        )
        raise ValueError(msg)
    if len(transforms) == NUM_TX_MAX:
        maybe_trans = transforms[1]
        if (maybe_trans.type) != "translation":
            msg = (
                "The second element of `coordinateTransformations` must be a "
                f"translation transform. Got {maybe_trans} instead."
            )
            raise ValueError(msg)

    return transforms

def ensure_axis_length(axes: Sequence[Axis]) -> Sequence[Axis]:
    """
    Ensures that there are between 2 and 5 axes (inclusive)
    """
    if (len_axes := len(axes)) not in VALID_NDIM:
        msg = f"Incorrect number of axes provided ({len_axes}). Only 2, 3, 4, or 5 axes are allowed."
        raise ValueError(msg)
    return axes


def ensure_axis_names(axes: Sequence[Axis]) -> Sequence[Axis]:
    """
    Ensures that the names of the axes are unique.
    """
    name_dupes = duplicates(a.name for a in axes)
    if len(name_dupes) > 0:
        msg = f"Axis names must be unique. Axis names {tuple(name_dupes.keys())} are repeated."
        raise ValueError(msg)
    return axes


def ensure_axis_types(axes: Sequence[Axis]) -> Sequence[Axis]:
    """
    Ensures that the following conditions are true:

    - there are only 2 or 3 axes with type `space`
    - the axes with type `space` are last in the list of axes
    - there is only 1 axis with type `time`
    - there is only 1 axis with type `channel`
    - there is only 1 axis with a type that is not `space`, `time`, or `channel`
    """
    axis_types = [ax.type for ax in axes]
    type_census = Counter(axis_types)
    num_spaces = type_census["space"]
    if num_spaces < 2 or num_spaces > 3:
        msg = f"Invalid number of space axes: {num_spaces}. Only 2 or 3 space axes are allowed."
        raise ValueError(msg)

    if not all(a == "space" for a in axis_types[-num_spaces:]):
        msg = f"Space axes must come last. Got axes with order: {axis_types}."
        raise ValueError(msg)

    if (num_times := type_census["time"]) > 1:
        msg = f"Invalid number of time axes: {num_times}. Only 1 time axis is allowed."
        raise ValueError(msg)

    if (num_channels := type_census["channel"]) > 1:
        msg = f"Invalid number of channel axes: {num_channels}. Only 1 channel axis is allowed."
        raise ValueError(msg)

    custom_axes = set(axis_types) - set(AxisType._member_names_)
    if (num_custom := len(custom_axes)) > 1:
        msg = f"Invalid number of custom axes: {num_custom}. Only 1 custom axis is allowed."
        raise ValueError(msg)
    return axes

class Dataset(Base):
    """
    Model for an element of `Multiscale.datasets`.

    See https://ngff.openmicroscopy.org/0.4/#multiscale-md
    """

    # TODO: validate that path resolves to an actual zarr array
    path: str
    # TODO: validate that transforms are consistent w.r.t dimensionality
    coordinateTransformations: Annotated[
        tuple[VectorScale | PathScale] | tuple[VectorScale | PathScale, VectorTranslation | PathTranslation],
        AfterValidator(ensure_scale_translation),
        AfterValidator(ensure_transform_dimensionality),
    ]



class Multiscale(Base):
    """
    Model for an element of `NgffImageMeta.multiscales`.

    See https://ngff.openmicroscopy.org/0.4/#multiscale-md.
    """

    datasets: tuple[Dataset, ...] = Field(..., min_length=1)
    version: Any | None = None
    # TODO: validate correctness of axes
    # TODO: validate uniqueness of axes
    axes: Annotated[
        tuple[Axis, ...],
        AfterValidator(ensure_axis_length),
        AfterValidator(ensure_axis_names),
        AfterValidator(ensure_axis_types),
    ]
    coordinateTransformations: (
        tuple[VectorScale | PathScale]
        | tuple[VectorScale | PathScale, VectorTranslation | PathTranslation]
        | None
    ) = None
    metadata: Any = None
    name: Any | None = None
    type: Any = None



class MultiscaleGroupAttrs(Base):
    """
    Model for the metadata of a NGFF image.

    See https://ngff.openmicroscopy.org/0.4/#image-layout.
    """

    multiscales: list[Multiscale] = Field(
        ...,
        description="The multiscale datasets for this image",
        min_length=1,
    )
    omero: Omero | None = None
    _check_unique = field_validator("multiscales")(_unique_items_validator)


class MultiscaleGroup(GroupSpec[MultiscaleGroupAttrs, ArraySpec | GroupSpec]):
    @classmethod
    def from_zarr(cls, node: zarr.Group) -> MultiscaleGroup:
        """
        Create an instance of `Group` from a `node`, a `zarr.Group`. This method discovers Zarr arrays in the hierarchy rooted at `node` by inspecting the OME-NGFF
        multiscales metadata.

        Parameters
        ---------
        node: zarr.Group
            A Zarr group that has valid OME-NGFF multiscale metadata.

        Returns
        -------
        Group
            A model of the Zarr group.
        """
        # on unlistable storage backends, the members of this group will be {}
        raise NotImplementedError
        guess = GroupSpec.from_zarr(node, depth=0)

        try:
            multi_meta_maybe = guess.attributes["multiscales"]
        except KeyError as e:
            store_path = get_path(node.store)
            msg = (
                "Failed to find mandatory `multiscales` key in the attributes of the Zarr group at "
                f"{node.store}://{store_path}://{node.path}."
            )
            raise KeyError(msg) from e

        multi_meta = MultiscaleGroupAttrs(multiscales=multi_meta_maybe)
        members_tree_flat = {}
        for multiscale in multi_meta.multiscales:
            for dataset in multiscale.datasets:
                array_path = f"{node.path}/{dataset.path}"
                try:
                    array = zarr.open_array(store=node.store, path=array_path, mode="r")
                    array_spec = ArraySpec.from_zarr(array)
                except ArrayNotFoundError as e:
                    msg = (
                        f"Expected to find an array at {array_path}, "
                        "but no array was found there."
                    )
                    raise ValueError(msg) from e
                except ContainsGroupError as e:
                    msg = (
                        f"Expected to find an array at {array_path}, "
                        "but a group was found there instead."
                    )
                    raise ValueError(msg) from e
                members_tree_flat["/" + dataset.path] = array_spec
        members_normalized = GroupSpec.from_flat(members_tree_flat)

        guess_inferred_members = guess.model_copy(
            update={"members": members_normalized.members}
        )
        return cls(**guess_inferred_members.model_dump())