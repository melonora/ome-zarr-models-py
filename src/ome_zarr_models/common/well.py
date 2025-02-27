from ome_zarr_models.base import BaseAttrs
from ome_zarr_models.v04.well_types import WellMeta


class WellAttrs(BaseAttrs):
    """
    Attributes for a well group.
    """

    well: WellMeta
