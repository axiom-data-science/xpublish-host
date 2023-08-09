import logging
from pathlib import Path

import xarray as xr

L = logging.getLogger(__name__)


def load_dataset_zarr(json_path: str | Path,):

    ds = xr.open_dataset(
        "reference://", engine="zarr",
        backend_kwargs={
            "storage_options": {
                "fo": json_path,
            },
            "consolidated": False
        }
    )
    return ds
