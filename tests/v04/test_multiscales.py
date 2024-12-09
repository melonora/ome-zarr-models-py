from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest
from pydantic import ValidationError
from pydantic_zarr.v2 import ArraySpec, GroupSpec
from tests.v04.conftest import from_array_props, from_arrays

from ome_zarr_models.v04._image_old import Image
from ome_zarr_models.v04.axes import Axis
from ome_zarr_models.v04.coordinate_transformations import (
    VectorScale,
    VectorTranslation,
    _build_transforms,
)
from ome_zarr_models.v04.image import ImageAttrs
from ome_zarr_models.v04.multiscales import (
    Dataset,
    Multiscale,
)

if TYPE_CHECKING:
    from typing import Literal


@pytest.fixture
def default_multiscale() -> Multiscale:
    axes = (
        Axis(name="c", type="channel", unit=None),
        Axis(name="z", type="space", unit="meter"),
        Axis(name="x", type="space", unit="meter"),
        Axis(name="y", type="space", unit="meter"),
    )
    rank = len(axes)
    transforms_top = _build_transforms(scale=(1,) * rank, translation=None)
    transforms_dset = _build_transforms(scale=(1,) * rank, translation=(0,) * rank)
    num_datasets = 3
    datasets = tuple(
        Dataset(path=f"path{idx}", coordinateTransformations=transforms_dset)
        for idx in range(num_datasets)
    )

    multi = Multiscale(
        axes=axes,
        datasets=datasets,
        coordinateTransformations=transforms_top,
    )
    return multi


def test_multiscale_unique_axis_names() -> None:
    # make axis names collide
    axes = (
        Axis(name="x", type="space", unit="meter"),
        Axis(name="x", type="space", unit="meter"),
    )
    rank = len(axes)
    datasets = (Dataset.build(path="path", scale=(1,) * rank, translation=(0,) * rank),)

    with pytest.raises(ValidationError, match="Axis names must be unique."):
        Multiscale(
            axes=axes,
            datasets=datasets,
            coordinateTransformations=_build_transforms(scale=(1, 1), translation=None),
        )


@pytest.mark.parametrize(
    "axis_types",
    [
        ("space", "space", "channel"),
        ("space", "channel", "space", "channel"),
    ],
)
def test_multiscale_space_axes_last(axis_types: list[str | None]) -> None:
    units_map = {"space": "meter", "time": "second"}
    axes = tuple(
        Axis(name=str(idx), type=t, unit=units_map.get(t))
        for idx, t in enumerate(axis_types)
    )
    rank = len(axes)
    datasets = (Dataset.build(path="path", scale=(1,) * rank, translation=(0,) * rank),)
    # TODO: make some axis-specifc exceptions
    with pytest.raises(ValidationError, match="Space axes must come last."):
        Multiscale(
            axes=axes,
            datasets=datasets,
            coordinateTransformations=_build_transforms(
                scale=(1,) * rank, translation=None
            ),
        )


@pytest.mark.parametrize("num_axes", [0, 1, 6, 7])
def test_multiscale_axis_length(num_axes: int) -> None:
    rank = num_axes
    axes = tuple(
        Axis(name=str(idx), type="space", unit="meter") for idx in range(num_axes)
    )
    datasets = (Dataset.build(path="path", scale=(1,) * rank, translation=(0,) * rank),)
    with pytest.raises(ValidationError, match="Incorrect number of axes provided"):
        Multiscale(
            axes=axes,
            datasets=datasets,
            coordinateTransformations=_build_transforms(
                scale=(1,) * rank, translation=None
            ),
        )


@pytest.mark.parametrize(
    "scale, translation", [((1, 1), (1, 1, 1)), ((1, 1, 1), (1, 1))]
)
def test_transform_invalid_ndims(
    scale: tuple[int, ...], translation: tuple[int, ...]
) -> None:
    with pytest.raises(
        ValidationError,
        match="The transforms have inconsistent dimensionality.",
    ):
        Dataset.build(path="foo", scale=scale, translation=translation)


@pytest.mark.parametrize(
    "transforms",
    [
        (
            VectorScale.build((1, 1, 1)),
            VectorTranslation.build((1, 1, 1)),
            VectorTranslation.build((1, 1, 1)),
        ),
        (VectorScale.build((1, 1, 1)),) * 5,
    ],
)
def test_transform_invalid_length(
    transforms: tuple[Any, ...],
) -> None:
    with pytest.raises(
        ValidationError, match=f"after validation, not {len(transforms)}"
    ):
        Dataset(path="foo", coordinateTransformations=transforms)


@pytest.mark.parametrize(
    "transforms",
    [
        (VectorTranslation.build((1, 1, 1)),) * 2,
        (
            VectorTranslation.build((1, 1, 1)),
            VectorScale.build((1, 1, 1)),
        ),
    ],
)
def test_transform_invalid_first_element(
    transforms: tuple[Any, Any],
) -> None:
    with pytest.raises(
        ValidationError,
        match="Input should be a valid dictionary or instance of VectorScale",
    ):
        Dataset(path="foo", coordinateTransformations=transforms)


@pytest.mark.parametrize(
    "transforms",
    (
        (
            VectorScale.build((1, 1, 1)),
            VectorScale.build((1, 1, 1)),
        ),
    ),
)
def test_transform_invalid_second_element(
    transforms: tuple[VectorScale, VectorScale],
) -> None:
    with pytest.raises(
        ValidationError,
        match="Input should be a valid dictionary or instance of VectorTranslation",
    ):
        Dataset(path="foo", coordinateTransformations=transforms)


def test_validate_axes_top_transforms() -> None:
    """
    Test that the number of axes must match the dimensionality of the
    top-level coordinateTransformations
    """
    axes_rank = 3
    tforms_rank = 2
    msg_expect = (
        f"The length of axes does not match the dimensionality of "
        f"the scale transform in coordinateTransformations. "
        f"Got {axes_rank} axes, but the scale transform has "
        f"dimensionality {tforms_rank}"
    )
    with pytest.raises(
        ValidationError,
        match=msg_expect,
    ):
        Multiscale(
            name="foo",
            axes=[Axis(name=str(idx), type="space") for idx in range(axes_rank)],
            datasets=(
                Dataset.build(
                    path="foo", scale=(1,) * axes_rank, translation=(0,) * axes_rank
                ),
            ),
            coordinateTransformations=_build_transforms(
                scale=(1,) * tforms_rank, translation=None
            ),
        )


def test_validate_axes_dset_transforms() -> None:
    """
    Test that the number of axes must match the dimensionality of the
    per-dataset coordinateTransformations
    """
    axes_rank = 3
    tforms_rank = 2
    axes = [Axis(name=str(idx), type="space") for idx in range(axes_rank)]

    msg_expect = (
        f"The length of axes does not match the dimensionality of "
        f"the scale transform in datasets[0].coordinateTransformations. "
        f"Got {axes_rank} axes, but the scale transform has "
        f"dimensionality {tforms_rank}"
    )

    with pytest.raises(
        ValidationError,
        match=re.escape(msg_expect),
    ):
        Multiscale(
            name="foo",
            axes=axes,
            datasets=[
                Dataset.build(
                    path="foo", scale=(1,) * tforms_rank, translation=(0,) * tforms_rank
                )
            ],
            coordinateTransformations=_build_transforms(
                scale=(1,) * axes_rank, translation=None
            ),
        )


@pytest.mark.skip
def test_multiscale_group_datasets_exist(
    default_multiscale: Multiscale,
) -> None:
    group_attrs = ImageAttrs(multiscales=(default_multiscale,))
    good_items = {
        d.path: ArraySpec(
            shape=(1, 1, 1, 1),
            dtype="uint8",
            chunks=(1, 1, 1, 1),
        )
        for d in default_multiscale.datasets
    }
    Image(attributes=group_attrs, members=good_items)

    bad_items = {
        d.path + "x": ArraySpec(
            shape=(1, 1, 1, 1),
            dtype="uint8",
            chunks=(1, 1, 1, 1),
        )
        for d in default_multiscale.datasets
    }

    with pytest.raises(
        ValidationError,
        match="array with that name was found in the hierarchy",
    ):
        Image(attributes=group_attrs, members=bad_items)


def test_multiscale_group_datasets_ndim() -> None:
    """
    Test that creating a Image with arrays with mismatched shapes raises
    an exception
    """
    true_ndim = 2
    bad_ndim = 3
    match = (
        f"The multiscale metadata has {true_ndim} axes "
        "which does not match the dimensionality of the array "
        f"found in this group at {bad_ndim} ({bad_ndim}). "
        "The number of axes must match the array dimensionality."
    )
    with pytest.raises(ValidationError, match=re.escape(match)):
        _ = from_array_props(
            shapes=((10,) * true_ndim, (10,) * bad_ndim),
            chunks=((1,) * true_ndim, (1,) * bad_ndim),
            dtype="uint8",
            paths=(str(true_ndim), str(bad_ndim)),
            axes=(Axis(name="x", type="space"), Axis(name="y", type="space")),
            scales=((1, 1), (2, 2)),
            translations=((0, 0), (0.5, 0.5)),
        )


def test_multiscale_group_missing_arrays() -> None:
    """
    Test that creating a multiscale group fails when an expected Zarr array is missing
    """
    arrays = np.zeros((10, 10)), np.zeros((5, 5))
    array_names = ("s0", "s1")
    group_model = from_arrays(
        arrays=arrays,
        axes=(Axis(name="x", type="space"), Axis(name="y", type="space")),
        paths=array_names,
        scales=((1, 1), (2, 2)),
        translations=((0, 0), (0.5, 0.5)),
    )
    # remove an array, then re-create the model
    group_model_broken = group_model.model_copy(
        update={"members": {array_names[0]: group_model.members[array_names[0]]}}
    )
    with pytest.raises(
        ValidationError,
        match=(
            "The multiscale metadata references an array that does "
            "not exist in this "
        ),
    ):
        Image(**group_model_broken.model_dump())


def test_multiscale_group_ectopic_group() -> None:
    """
    Test that creating a multiscale group fails when an expected Zarr array
    is actually a group
    """
    arrays = np.zeros((10, 10)), np.zeros((5, 5))
    array_names = ("s0", "s1")
    group_model = from_arrays(
        arrays=arrays,
        axes=(Axis(name="x", type="space"), Axis(name="y", type="space")),
        paths=array_names,
        scales=((1, 1), (2, 2)),
        translations=((0, 0), (0.5, 0.5)),
    )
    # remove an array, then re-create the model
    group_model_broken = group_model.model_copy(
        update={"members": {array_names[0]: GroupSpec()}}
    )
    with pytest.raises(
        ValidationError,
        match=re.escape(f"The node at {array_names[0]} is a group, not an array."),
    ):
        Image(**group_model_broken.model_dump())


@pytest.mark.parametrize("store", ["memory"], indirect=True)
def test_from_zarr_missing_metadata(
    store: Literal["memory"],
    request: pytest.FixtureRequest,
) -> None:
    group_model = GroupSpec()
    group = group_model.to_zarr(store, path="test")
    store_path = store.path if hasattr(store, "path") else ""
    match = (
        "Failed to find mandatory `multiscales` key in the attributes of the "
        f"Zarr group at {store}://{store_path}://{group.path}."
    )
    with pytest.raises(KeyError, match=match):
        Image.from_zarr(group)


@pytest.mark.parametrize("store", ["memory"], indirect=True)
def test_from_zarr_missing_array(store: Literal["memory"]) -> None:
    """
    Test that creating a multiscale Group fails when an expected Zarr array is missing
    or is a group instead of an array
    """
    arrays = np.zeros((10, 10)), np.zeros((5, 5))
    group_path = "broken"
    arrays_names = ("s0", "s1")
    group_model = from_arrays(
        arrays=arrays,
        axes=(Axis(name="x", type="space"), Axis(name="y", type="space")),
        paths=arrays_names,
        scales=((1, 1), (2, 2)),
        translations=((0, 0), (0.5, 0.5)),
    )

    # make an untyped model, and remove an array before serializing
    removed_array_path = arrays_names[0]
    model_dict = group_model.model_dump(exclude={"members": {removed_array_path: True}})
    broken_group = GroupSpec(**model_dict).to_zarr(store=store, path=group_path)
    match = (
        f"Expected to find an array at {group_path}/{removed_array_path}, "
        "but no array was found there."
    )
    with pytest.raises(ValueError, match=match):
        Image.from_zarr(broken_group)


@pytest.mark.parametrize("store", ["memory"], indirect=True)
def test_from_zarr_ectopic_group(store: Literal["memory"]) -> None:
    """
    Test that creating a multiscale Group fails when an expected Zarr array is missing
    or is a group instead of an array
    """
    arrays = np.zeros((10, 10)), np.zeros((5, 5))
    group_path = "broken"
    arrays_names = ("s0", "s1")
    group_model = from_arrays(
        arrays=arrays,
        axes=(Axis(name="x", type="space"), Axis(name="y", type="space")),
        paths=arrays_names,
        scales=((1, 1), (2, 2)),
        translations=((0, 0), (0.5, 0.5)),
    )

    # make an untyped model, and remove an array before serializing
    removed_array_path = arrays_names[0]
    model_dict = group_model.model_dump(exclude={"members": {removed_array_path: True}})
    broken_group = GroupSpec(**model_dict).to_zarr(store=store, path=group_path)

    # put a group where the array should be
    broken_group.create_group(removed_array_path)
    match = (
        f"Expected to find an array at {group_path}/{removed_array_path}, "
        "but a group was found there instead."
    )
    with pytest.raises(ValueError, match=match):
        Image.from_zarr(broken_group)


@pytest.mark.skip
def test_hashable(default_multiscale: Multiscale) -> None:
    """
    Test that `Multiscale` can be hashed
    """
    assert set(default_multiscale) == set(default_multiscale)
