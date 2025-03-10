import pytest

from ome_zarr_models._rfc5_transforms.coordinate_transformations import (
    CoordinateSystem,
    CoordinateTransformation,
    SpatialMapper,
)
from ome_zarr_models.common.axes import Axis
from tests._rfc5_transforms.conftest import T, _parse_data, get_data_folder

FOLDER = get_data_folder(__file__)


@_parse_data(
    folder=FOLDER,
    in_memory=SpatialMapper(
        coordinateSystems=[
            CoordinateSystem(
                name="in",
                axes=[
                    Axis(name="j"),
                    Axis(name="i"),
                ],
            ),
            CoordinateSystem(
                name="out",
                axes=[
                    Axis(name="y"),
                    Axis(name="x"),
                ],
            ),
            CoordinateSystem(
                name="out2",
                axes=[
                    Axis(name="y"),
                    Axis(name="x"),
                ],
            ),
        ],
        coordinateTransformations=[
            CoordinateTransformation(type="identity", input="in", output="out")
        ],
    ),
)
def test_identity(parsed: type[T]) -> None:
    pass


@pytest.mark.skip
def test_scale() -> None:
    pass


@pytest.mark.skip
def test_translation() -> None:
    pass


@pytest.mark.skip
def test_sequence() -> None:
    pass


@pytest.mark.skip
def test_rotation() -> None:
    pass


@pytest.mark.skip
def test_affine2d2d() -> None:
    pass


@pytest.mark.skip
def test_affine2d3d() -> None:
    pass


@pytest.mark.skip
def test_mapAxis1() -> None:
    pass


@pytest.mark.skip
def test_mapAxis2() -> None:
    pass


@pytest.mark.skip
def test_byDimension1() -> None:
    pass


@pytest.mark.skip
def test_byDimension2() -> None:
    pass


@pytest.mark.skip
def test_byDimensionInvalid1() -> None:
    pass


@pytest.mark.skip
def test_byDimensionInvalid2() -> None:
    pass


@pytest.mark.skip
def test_displacement1d() -> None:
    pass


@pytest.mark.skip
def test_inverseOf() -> None:
    pass


@pytest.mark.skip
def test_coordinates1d() -> None:
    pass


@pytest.mark.skip
def test_sequenceSubspace1() -> None:
    pass


@pytest.mark.skip
def test_bijection() -> None:
    pass


@pytest.mark.skip
def test_bijection_verbose() -> None:
    pass


@pytest.mark.skip
def test_xarrayLike() -> None:
    pass


@pytest.mark.skip
def test_byDimensionXarray() -> None:
    pass
