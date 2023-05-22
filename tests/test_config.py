import logging
import os

import pytest

from xpublish_host.config import PluginConfig
from xpublish_host.plugins import DatasetConfig

from .utils import HostTesting, simple_loader

L = logging.getLogger(__name__)


class SimpleDataset(HostTesting):

    @pytest.fixture(scope='module')
    def varname(self):
        return 'count'

    @pytest.fixture(scope='module')
    def dataset(self):
        return simple_loader()

    @pytest.fixture(scope='module')
    def loader(self, dataset):
        def load():
            return dataset
        return load


class TestDatasetConfigKwargs(SimpleDataset):

    @pytest.fixture(scope='module')
    def datasets_config(self, dataset_id, loader):
        dc = DatasetConfig(
            id=dataset_id,
            title='Title',
            description='Description',
            loader=loader,
        )
        yield { dataset_id: dc }


class TestDatasetConfigEnvVars(SimpleDataset):

    @pytest.fixture(scope='module')
    def loader(self):
        return simple_loader

    @pytest.fixture(scope="module")
    def env(self, dataset_id, loader):

        envvars = {
            'XPUB_PLUGINS_CONFIG__DCONFIG__MODULE': 'xpublish_host.plugins.DatasetsConfigPlugin',
            f'XPUB_PLUGINS_CONFIG__DCONFIG__KWARGS__DATASETS_CONFIG__{dataset_id}__ID': dataset_id,
            f'XPUB_PLUGINS_CONFIG__DCONFIG__KWARGS__DATASETS_CONFIG__{dataset_id}__TITLE': 'Title',
            f'XPUB_PLUGINS_CONFIG__DCONFIG__KWARGS__DATASETS_CONFIG__{dataset_id}__DESCRIPTION': 'Description',
            f'XPUB_PLUGINS_CONFIG__DCONFIG__KWARGS__DATASETS_CONFIG__{dataset_id}__LOADER': f"{loader.__module__}.{loader.__name__}",
        }

        for k, v in envvars.items():
            os.environ[k] = v

    @pytest.fixture(scope='module')
    def plugins_config(self):
        return {
            'zarr': PluginConfig(
                module='xpublish.plugins.included.zarr.ZarrPlugin',
            )
        }


class TestDatasetConfigEnvFile(SimpleDataset):

    @pytest.fixture(scope='module')
    def loader(self):
        return simple_loader

    @pytest.fixture(scope='module')
    def env(self, dataset_id, tmpdir_factory, loader):
        fn = tmpdir_factory.mktemp("config").join(".env")

        envvars = [
            'XPUB_PLUGINS_CONFIG__DCONFIG__MODULE=xpublish_host.plugins.DatasetsConfigPlugin',
            f'XPUB_PLUGINS_CONFIG__DCONFIG__KWARGS__DATASETS_CONFIG__{dataset_id}__ID={dataset_id}',
            f'XPUB_PLUGINS_CONFIG__DCONFIG__KWARGS__DATASETS_CONFIG__{dataset_id}__TITLE=Title',
            f'XPUB_PLUGINS_CONFIG__DCONFIG__KWARGS__DATASETS_CONFIG__{dataset_id}__DESCRIPTION=Description',
            f'XPUB_PLUGINS_CONFIG__DCONFIG__KWARGS__DATASETS_CONFIG__{dataset_id}__LOADER={loader.__module__}.{loader.__name__}',
        ]
        with fn.open('wt') as f:
            f.writelines([ f'{e}\n' for e in envvars] )

        os.environ['XPUB_ENV_FILES'] = str(fn)

    @pytest.fixture(scope='module')
    def plugins_config(self):
        return {
            'zarr': PluginConfig(
                module='xpublish.plugins.included.zarr.ZarrPlugin',
            )
        }


class TestDatasetConfigConfigFile(SimpleDataset):

    @pytest.fixture(scope='module')
    def plugins_config(self, tmpdir_factory):

        yaml = """
        datasets_config:
            ds:
                id: ds
                title: Static
                description: Static dataset that is never reloaded
                loader: xpublish_host.examples.datasets.simple
        """

        dsc = tmpdir_factory.mktemp("config").join("simple.yaml")
        with dsc.open('wt') as f:
            f.write(yaml)

        return {
            'zarr': PluginConfig(
                module='xpublish.plugins.included.zarr.ZarrPlugin',
            ),
            'dconfig': PluginConfig(
                module='xpublish_host.plugins.DatasetsConfigPlugin',
                kwargs=dict(
                    datasets_config_file=str(dsc)
                )
            )
        }
