import io
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Sequence

from fastapi import (
    APIRouter,
    Depends,
    Query,
    Response,
)
from fastapi.responses import StreamingResponse

from xpublish.plugins import (
    Dependencies,
    Plugin,
    hookimpl,
)
from xpublish_host.utils import CommaSeparatedList

L = logging.getLogger(__name__)


def utc_native_dt(dt):
    if isinstance(dt, datetime):
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class DataFormat(str, Enum):
    JSONL = ".jsonl"
    DICT = '.dict'
    LIST = '.list'
    SPLIT = '.split'
    TIGHT = '.tight'
    RECORDS = '.records'
    INDEX = '.index'
    PARQUET = '.parquet'


class DataPointsPlugin(Plugin):
    """Adds an Data Point Extraction endpoint"""

    name = 'data_points'

    dataset_router_prefix: str = '/data_points'
    dataset_router_tags: Sequence[str] = ['data_points']

    @hookimpl
    def dataset_router(self, deps: Dependencies):

        def grid_params(
            x_var: Annotated[str | None, Query()] = None,
            y_var: Annotated[str | None, Query()] = None,
        ):
            return {
                'x_var': x_var,
                'y_var': y_var,
            }

        def depth_params(
            depth_var: Annotated[str | None, Query()] = None,
            depth_start: Annotated[float | None, Query()] = 0,
            depth_end: Annotated[float | None, Query()] = 1,
        ):
            return {
                'var': depth_var,
                'start': depth_start,
                'end': depth_end,
            }

        def time_params(
            time_var: Annotated[str | None, Query()] = None,
            time_start: Annotated[datetime | None, Query()] = None,
            time_end: Annotated[datetime | None, Query()] = None,
        ):
            return {
                'var': time_var,
                'start': utc_native_dt(time_start),
                'end': utc_native_dt(time_end)
            }

        def var_params(
            var: Annotated[CommaSeparatedList[str] | None, Query()] = None,
            keep: Annotated[CommaSeparatedList[str] | None, Query()] = None,
            return_null: Annotated[bool, Query()] = False,
        ):
            return {
                'var': var,
                'keep': keep,
                'return_null': return_null,
            }

        router = APIRouter(prefix=self.dataset_router_prefix, tags=list(self.dataset_router_tags))

        @router.get('/filter{fmt}', summary="Gets data points between 2 times for a list of variables")
        async def get_points(
            fmt: DataFormat = '.jsonl',
            dataset=Depends(deps.dataset),
            time_params=Depends(time_params),
            depth_params=Depends(depth_params),
            var_params=Depends(var_params),
            grid_params=Depends(grid_params),
        ):

            selection = {}
            renames = {}

            if time_params['var']:

                renames[time_params['var']] = 't'

                if time_params['var'] in dataset.dims:
                    selection[time_params['var']] = slice(
                        time_params['start'],
                        time_params['end']
                    )
                else:
                    L.warning(f"'{ time_params['var']}' not found in dataset dimensions")

            if depth_params['var']:

                renames[depth_params['var']] = 'z'

                if depth_params['var'] in dataset.dims:
                    selection[depth_params['var']] = slice(
                        depth_params['start'],
                        depth_params['end']
                    )
                else:
                    L.warning(f"'{ depth_params['var']}' not found in dataset dimensions")

            if grid_params['x_var']:
                renames[grid_params['x_var']] = 'x'

            if grid_params['y_var']:
                renames[grid_params['y_var']] = 'y'

            # How far back to return data for
            ds = dataset.sel(selection)

            # Subset to requested variables
            if var_params['var']:
                ds = ds[var_params['var']]

            # Convert to a dataframe
            df = ds.to_dataframe().reset_index()

            axis_vars = [
                renames.get(time_params['var'], None),
                renames.get(depth_params['var'], None),
                renames.get(grid_params['x_var'], None),
                renames.get(grid_params['y_var'], None),
            ]
            axis_vars = [ x for x in axis_vars if x ]

            keep = axis_vars.copy()
            keep += var_params['var'] or []
            keep += var_params['keep'] or []

            if var_params['return_null'] is False:
                df = df.dropna(how='all', subset=var_params['var'])

            df = df.reset_index(drop=True)

            # standardize axes
            if renames:
                df = df.rename(columns=renames)

            df = df.drop(columns=[ c for c in df.columns if c not in keep ])

            if fmt == DataFormat.JSONL:
                data = df.to_json(
                    orient='records',
                    lines=True,
                    date_format='iso',
                )
                return Response(
                    data,
                    media_type='application/jsonlines+json'
                )
            elif fmt == DataFormat.PARQUET:

                data = io.BytesIO()
                df.to_parquet(
                    data,
                    index=None,
                )

                def stream():
                    data.seek(0)
                    yield from data

                return StreamingResponse(
                    stream(),
                    # https://issues.apache.org/jira/browse/PARQUET-1889
                    media_type="application/vnd.apache.parquet"
                )
            else:
                if fmt in [
                    DataFormat.SPLIT,
                    DataFormat.TIGHT,
                ]:
                    if axis_vars:
                        df = df.set_index(axis_vars)

                data = df.to_dict(
                    orient=fmt[1:]  # strip out the leading period,
                )
                return data

        return router
