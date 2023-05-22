import logging
import os
import typing as t
from datetime import datetime, timezone

import xarray as xr
from goodconf import GoodConf
from pydantic import (
    BaseModel,
    FilePath,
    PyObject,
)

from xpublish import Plugin, hookimpl
from xpublish_host.config import RestConfig

try:
    from prometheus_client import Counter, Gauge

    from xpublish_host.metrics import DEFAULT_LABELS, create_metric
    metrics = True
    DATASET_LOAD_TIME = create_metric(
        Gauge,
        "dataset_load_time",
        "How long it look to last load the dataset",
        ["dataset"],
    )
    DATASET_LOAD_COUNT = create_metric(
        Counter,
        "dataset_load_count",
        "How many times a dataset has been loaded",
        ["dataset"],
    )
    DATASET_LOAD_WHEN = create_metric(
        Gauge,
        "dataset_load_when",
        "When the dataset was last loaded",
        ["dataset"],
    )
except ImportError:
    metrics = False

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


class DatasetConfigFile(GoodConf):
    datasets_config: dict[str, DatasetConfig] = {}


class DatasetsConfigPlugin(Plugin):

    name = 'dconfig'

    datasets_config: dict[str, DatasetConfig] = {}
    datasets_config_file: FilePath = None

    __datasets: dict = {}
    __datasets_loaded: dict = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        config_file_datasets = self.load_config_file()

        self.datasets_config.update(config_file_datasets)

        for dsc in self.datasets_config.values():
            if dsc.skip_initial_load is False:
                L.info(f"Loading dataset (initial): {dsc.id}")
                _ = self.load_dataset(dsc)

    def load_config_file(self):
        # Load a config file into a dict of DatasetConfigs
        dcf = DatasetConfigFile(load=True)

        # Look for env file pointing to a config file
        yaml_config = os.environ.get('XPUBDC_CONFIG_FILE', None)
        if yaml_config and os.path.exists(yaml_config):
            dcf.load(yaml_config)

        if self.datasets_config_file and os.path.exists(self.datasets_config_file):
            dcf.load(self.datasets_config_file)

        if dcf.datasets_config:
            return dcf.datasets_config

        return {}

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
        now = datetime.utcnow().timestamp()
        dataset = config.load()

        if metrics is True:
            after = datetime.utcnow().timestamp()
            elapsed = after - now
            DATASET_LOAD_TIME.labels(dataset=config.id, **DEFAULT_LABELS).set(elapsed)
            DATASET_LOAD_WHEN.labels(dataset=config.id, **DEFAULT_LABELS).set(after)
            DATASET_LOAD_COUNT.labels(dataset=config.id, **DEFAULT_LABELS).inc()

        self.__datasets[config.id] = dataset
        self.__datasets_loaded[config.id] = now
        return self.__datasets[config.id]
