import logging
from datetime import datetime, timezone

import xarray as xr

from xpublish import Plugin, hookimpl
from xpublish_host.config import DatasetConfig

L = logging.getLogger(__name__)


class DatasetsConfigPlugin(Plugin):
    name = 'datasets_config'

    datasets_config: dict[str, DatasetConfig] = {}

    datasets: dict = {}
    datasets_loaded: dict = {}

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
            last_updated = self.datasets_loaded.get(dataset_id, 0)
            now = datetime.now(timezone.utc).timestamp()
            expiration_check = (now - last_updated) < dsc.invalidate_after

        if dataset_id in self.datasets and cache_check and expiration_check:
            return self.datasets[dataset_id]

        # If we got here, load the dataset
        L.info(f"Loading dataset: {dsc.id}")
        now = datetime.now(timezone.utc).timestamp()
        dataset = dsc.load()

        self.datasets[dataset_id] = dataset
        self.datasets_loaded[dataset_id] = now

        return self.datasets[dataset_id]
