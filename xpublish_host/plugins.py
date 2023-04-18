import logging
import typing as t
from datetime import datetime, timezone

import xarray as xr
from pydantic import BaseModel, PyObject

from xpublish import Plugin, hookimpl
from xpublish_host.config import RestConfig

L = logging.getLogger(__name__)


class DatasetConfig(BaseModel):
    id: str
    title: str
    description: str
    loader: PyObject
    args: list[t.Any] = ()
    kwargs: dict[str, t.Any] = {}
    invalidate_after: int | None = None
    skip_initial_load: bool = False

    def load(self):
        return self.loader(*self.args, **self.kwargs)

    def serve(self, **rest_kwargs):
        """
        Helper method to run a single dataset with configs
        """
        config = RestConfig(**rest_kwargs, load=True)
        rest = config.setup()
        rest.register_plugin(
            DatasetsConfigPlugin(
                dataset_config={self.id: self}
            ),
            overwrite=True
        )
        rest.serve(
            **config.serve_kwargs()
        )


class DatasetsConfigPlugin(Plugin):

    # class Config:
    #     env_file = os.environ.get('XPUBDC_ENV_FILES', '.env')
    #     env_prefix = 'XPUBDC_'
    #     env_nested_delimiter = '__'

    name = 'dconfig'

    datasets_config: dict[str, DatasetConfig] = {}

    __datasets: dict = {}
    __datasets_loaded: dict = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for dsc in self.datasets_config.values():
            if dsc.skip_initial_load is False:
                L.info(f"Loading dataset (initial): {dsc.id}")
                _ = self.load_dataset(dsc)

    @hookimpl
    def get_datasets(self):
        return [ v.id for v in self.datasets_config.values() ]

    @hookimpl
    def get_dataset(self, dataset_id: str) -> xr.Dataset:

        try:
            dsc = next(v for v in self.datasets_config.values() if v.id == dataset_id)
        except StopIteration:
            return

        # TODO: Cache check. We could potentially check a cache to see if this dataset
        # should be reloaded after a certain timeout or key expiration. This could be
        # set through an HTTP endpoint to invalidate a dataset's cache. This cache needs
        # to be on the per-process level since that is where the datasets are accessed
        cache_check = True

        # Expiration check, after X amount of time, invalidate the dataset
        expiration_check = True
        if dsc.invalidate_after is not None:
            last_updated = self.__datasets_loaded.get(dataset_id, 0)
            now = datetime.now(timezone.utc).timestamp()
            expiration_check = (now - last_updated) < dsc.invalidate_after

        if dataset_id in self.__datasets and cache_check and expiration_check:
            return self.__datasets[dataset_id]

        # If we got here, load the dataset
        L.info(f"Loading dataset: {dsc.id}")
        dataset = self.load_dataset(dsc)
        return dataset

    def load_dataset(self, config: DatasetConfig):
        now = datetime.now(timezone.utc).timestamp()
        dataset = config.load()
        self.__datasets[config.id] = dataset
        self.__datasets_loaded[config.id] = now
        return self.__datasets[config.id]
