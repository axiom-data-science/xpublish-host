import json
import os

import pytest

from xpublish_host.config import DatasetConfig, PluginConfig, RestConfig

from .utils import HostTesting, simple_loader


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


class TestSimpleDatasetKwargs(SimpleDataset):

    @pytest.fixture(scope='module')
    def datasets_config(self, loader):
        return {
            'ds1': DatasetConfig(
                id='TestID',
                title='TestTitle',
                description='TestDescription',
                loader=loader,
            )
        }


class TestDynamicDatasetKwargs(SimpleDataset):

    @pytest.fixture(scope='module')
    def id(self, rest_config):
        yield 'dynamic'

    @pytest.fixture(scope='module')
    def plugins_config(self, loader):
        return {
            'zarr': PluginConfig(
                module='xpublish.plugins.included.zarr.ZarrPlugin',
                kwargs=dict(
                    dataset_router_prefix='/zarr'
                )
            ),
            'dynamic': PluginConfig(
                module='xpublish_host.plugins.DatasetsConfigPlugin',
                kwargs=dict(
                    datasets_config={
                        'dyanmic': DatasetConfig(
                            id='dynamic',
                            title='TestTitle',
                            description='TestDescription',
                            loader=loader,
                        )
                    }
                )
            )
        }

    @pytest.fixture(scope='module')
    def rest_config(self, datasets_config, plugins_config):
        config = RestConfig(
            plugins_config=plugins_config,
        )
        yield config


class TestDatasetConfigJsonEnv(SimpleDataset):

    @pytest.fixture(scope='module')
    def loader(self):
        return simple_loader

    @pytest.fixture(scope="module")
    def env(self, loader):
        dsconfig = {
            'ds1': dict(
                id='TestID',
                title='TestTitle',
                description='TestDescription',
                loader=f'{loader.__module__}.{loader.__name__}',
            )
        }

        os.environ['XPUB_DATASETS_CONFIG'] = json.dumps(dsconfig)


class TestDatasetConfigEnv(SimpleDataset):

    @pytest.fixture(scope='module')
    def loader(self):
        return simple_loader

    @pytest.fixture(scope="module")
    def env(self, loader):
        os.environ['XPUB_DATASETS_CONFIG__DS1__ID'] = 'TestID'
        os.environ['XPUB_DATASETS_CONFIG__DS1__TITLE'] = 'TestTitle'
        os.environ['XPUB_DATASETS_CONFIG__DS1__DESCRIPTION'] = 'TestDescription'
        os.environ['XPUB_DATASETS_CONFIG__DS1__LOADER'] = f'{loader.__module__}.{loader.__name__}'


class TestLoaderOnlyEnv(SimpleDataset):

    @pytest.fixture(scope='module')
    def loader(self):
        return simple_loader

    @pytest.fixture(scope="module")
    def env(self, loader):
        os.environ['XPUB_DATASETS_CONFIG__DS1__LOADER'] = f'{loader.__module__}.{loader.__name__}'

    @pytest.fixture(scope='module')
    def datasets_config(self, env):
        return {
            'ds1': dict(
                id='TestID',
                title='TestTitle',
                description='TestDescription',
            )
        }


class TestDatasetConfigFile(SimpleDataset):

    @pytest.fixture(scope='module')
    def loader(self):
        return simple_loader

    @pytest.fixture(scope='module')
    def env(self, tmpdir_factory, loader):
        fn = tmpdir_factory.mktemp("config").join(".env")

        with fn.open('wt') as f:
            f.write(f'XPUB_DATASETS_CONFIG__DS1__LOADER="{loader.__module__}.{loader.__name__}"')
            f.write('XPUB_DATASETS_CONFIG__DS1__ID="TestID"')
            f.write('XPUB_DATASETS_CONFIG__DS1__TITLE="TestTitle"')
            f.write('XPUB_DATASETS_CONFIG__DS1__DESCRIPTION="TestDescription"')

        os.environ['XPUB_ENV_FILES'] = str(fn)


class TestLoaderOnlyFile(SimpleDataset):

    @pytest.fixture(scope='module')
    def loader(self):
        return simple_loader

    @pytest.fixture(scope='module')
    def env(self, tmpdir_factory, loader):
        fn = tmpdir_factory.mktemp("config").join(".env")

        with fn.open('wt') as f:
            f.write(f'XPUB_DATASETS_CONFIG__DS1__LOADER="{loader.__module__}.{loader.__name__}"')

        os.environ['XPUB_ENV_FILES'] = str(fn)

    @pytest.fixture(scope='module')
    def datasets_config(self, env):
        return {
            'ds1': dict(
                id='TestID',
                title='TestTitle',
                description='TestDescription',
            )
        }
