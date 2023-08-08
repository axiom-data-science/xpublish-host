import xarray as xr


def zarr(json_path: str | Path,):
    ds = xr.open_dataset(
    "reference://", engine="zarr",
    backend_kwargs={
        "storage_options": {
            "fo": json_path,
        },
        "consolidated": False
    }
)