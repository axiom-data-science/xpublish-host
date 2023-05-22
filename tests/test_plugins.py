import logging
import io

import pandas as pd
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


class TestDataPoints(SimpleDataset):

    @pytest.fixture(scope='module')
    def datasets_config(self, dataset_id, loader):
        dc = DatasetConfig(
            id=dataset_id,
            title='Title',
            description='Description',
            loader=loader,
        )
        yield { dataset_id: dc }

    @pytest.fixture(scope='module')
    def plugins_config(self, datasets_config):
        return {
            'zarr': PluginConfig(
                module='xpublish.plugins.included.zarr.ZarrPlugin',
            ),
            'dconfig': PluginConfig(
                module='xpublish_host.plugins.DatasetsConfigPlugin',
                kwargs=dict(
                    datasets_config=datasets_config
                )
            ),
            'data_points': PluginConfig(
                module='xpublish_host.plugins.DataPointsPlugin',
            ),
        }

    def test_data_points(self, dataset_id, client):
        response = client.get(
            f'/datasets/{dataset_id}/data_points/filter.parquet',
            params=dict(
                return_null=True,
                keep='count'
            )
        )
        assert response.status_code == 200

        df = pd.read_parquet(io.BytesIO(response.content))
        assert 'count' in df
        assert (df['count'] == pd.Series([1,2,3])).all()

    def test_scalar(self, dataset_id, client):
        response = client.get(
            f'/datasets/{dataset_id}/zarr/scalar/0',
            params=dict(
                return_null=True,
                keep='count'
            )
        )
        assert response.status_code == 200
