import logging
import typing as t
from operator import attrgetter
from pathlib import Path

import xarray as xr

L = logging.getLogger(__name__)


def load_mfdataset(
    root_path: str | Path,
    file_glob: str,
    open_mfdataset_kwargs: t.Dict = {},
    file_limit: int | None = None,
    skip_head_files: int | None = 0,
    skip_tail_files: int | None = 0,
    computes: list[str] | None = None,
    chunks: dict[str, int] | None = None,
    axes: dict[str, str] | None = None,
    sort_by: dict[str, str] | None = None,
    isel: dict[str, slice] | None = None,
    sel: dict[str, slice] | None = None,
    rechunk: bool = False,
    attrs_file_idx: int = -1,
    combine_by_coords: list[str | Path] = None,
    **kwargs
) -> xr.Dataset:

    # drops = drops or []
    computes = computes or []
    chunks = chunks or {}
    axes = axes or {}
    sort_by = sort_by or {}
    isel = isel or {}
    sel = sel or {}
    combine_by_coords = combine_by_coords or []

    root = Path(root_path)
    files = sorted(
        [
            p for p in root.glob(file_glob)
        ],
        key=attrgetter('name')
    )

    # Skip files from the front and back. If not defined
    # (None) this won't change the files list.
    if skip_tail_files:
        skip_tail_files = skip_tail_files * -1
    else:
        # Prevents a zero from not working as expected
        skip_tail_files = None

    files = files[skip_head_files:skip_tail_files]

    # You know, for testing
    if file_limit:
        files = files[-file_limit:]

    num_files = len(files)
    L.info(f"Found {num_files} files in {root_path}{file_glob}")
    if not num_files:
        return xr.Dataset()

    # Set a default chunking scheme if one was not provided
    # that uses all defined axes chunked by 'auto'
    axis_names = ['t', 'z', 'x', 'y']
    if not chunks:
        chunks = {
            axes.get(a, a): 'auto'
            for a in axis_names
            if a in axes and not chunks
        }
    L.info(f'Using chunking scheme: {chunks}')

    # Pull metadata from the last file unless a file was specified
    attrs_file = open_mfdataset_kwargs.pop('attrs_file', files[attrs_file_idx])

    # These are the default open_mfdataset_kwargs
    xr_kwargs = dict(
        parallel=True,
        engine='netcdf4',
        data_vars='minimal',
        coords='minimal',
        compat='override',
        combine='nested',
        concat_dim=[
            axes.get('t', 't')
        ],
        decode_cf=True,
        decode_times=True,
        decode_timedelta=False,
        chunks=chunks,
        attrs_file=attrs_file,
    )
    xr_kwargs.update(open_mfdataset_kwargs)

    L.info(f"Loading {num_files} files with {xr_kwargs}...")
    cache_size = max(num_files, 128)
    xr.set_options(file_cache_maxsize=cache_size)
    ds = xr.open_mfdataset(
        files,
        **xr_kwargs
    )

    if combine_by_coords:
        for combine_file in combine_by_coords:
            L.info(f"Combining {combine_file}...")
            combo = xr.open_dataset(
                combine_file,
                engine='netcdf4',
                drop_variables=xr_kwargs.get('drop_variables', [])
            )
            ds = xr.combine_by_coords(
                [combo, ds],
                compat='override',
                combine_attrs='override'
            )

    if sort_by:
        L.info(f"Sorting by {sort_by}...")
        ds = ds.sortby(sort_by)

    if isel:
        L.info("Selecting by index...")
        isels = {
            k: slice(*v) for k, v in isel.items()
        }
        ds = ds.isel(**isels)

    if sel:
        L.info("Selecting...")
        ds = ds.sel(**sel)

    if rechunk is True and chunks:
        L.info("Rechunking...")
        # Remove any dims that may have been squashed due to processing
        chunks = { k: v for k, v in chunks.items() if k in ds.dims }
        ds = ds.chunk(chunks)

    L.info("Computing and assigning axes as coordinates...")
    assigns = {}
    for _, aname in axes.items():
        assigns[aname] = ds[aname].compute()
    ds = ds.assign_coords(assigns)

    L.info("Computing variables...")
    for variable in computes:
        ds[variable] = ds[variable].compute()

    return ds
