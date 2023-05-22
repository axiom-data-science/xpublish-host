import os
from pathlib import Path

import pytest
import uvicorn
import xarray as xr
from fastapi.testclient import TestClient

import xpublish
from xpublish_host.config import PluginConfig, RestConfig


def simple_loader(*args, **kwargs):
    return xr.Dataset({'count': ('x', [1, 2, 3])})


def versions_check(client):
    response = client.get('/versions')
    assert response.status_code == 200
    assert response.json()['xarray'] == xr.__version__


def plugins_check(client):
    response = client.get('/plugins')
    assert response.status_code == 200
    plugins = response.json()

    assert 'dataset_info' in plugins
    assert 'module_version' in plugins
    assert 'plugin_info' in plugins
    assert 'zarr' in plugins
    assert 'intake' in plugins

    assert plugins['dataset_info']['version'] == xpublish.__version__


def datasets_check(client, dataset_id):
    response = client.get('/datasets')
    assert response.status_code == 200
    assert response.json() == [dataset_id]


def html_check(client, dataset_id):
    response = client.get(f'/datasets/{dataset_id}/')
    assert response.status_code == 200


def docs_check(client):
    response = client.get('/api')
    assert response.status_code == 200


def zarr_check(client, dataset_id, var_name):
    response = client.get(
        f'/datasets/{dataset_id}/zarr/.zmetadata'
    )
    assert response.status_code == 200

    response = client.get(
        f'/datasets/{dataset_id}/zarr/.zgroup'
    )
    assert response.status_code == 200

    response = client.get(
        f'/datasets/{dataset_id}/zarr/{var_name}/.zarray'
    )
    assert response.status_code == 200

    # check the number of dimensions
    var_info = client.get(f'/datasets/{dataset_id}/zarr/{var_name}/.zarray')
    if len(var_info.json()['shape']) == 3:
        response = client.get(f'/datasets/{dataset_id}/zarr/{var_name}/0.0.0')
    elif len(var_info.json()['shape']) == 4:
        response = client.get(f'/datasets/{dataset_id}/zarr/{var_name}/0.0.0.0')
    assert response.status_code == 200


def serve_check(config, rest, mocker):
    mocker.patch('uvicorn.run')
    rest.serve(**config.serve_kwargs())
    uvicorn.run.assert_called_once_with(
        rest.app,
        **config.serve_kwargs(),
    )


def files_count_mark(path, suffix):
    glb = f'**/*{suffix}'
    glb_str = Path(path) / glb
    return pytest.mark.skipif(
        len(list(Path(path).glob(glb))) == 0,
        reason=f"No test files found at {glb_str}"
    )


class HostTesting:

    @pytest.fixture(scope='module')
    def varname(self):
        pass

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
            )
        }

    @pytest.fixture(scope='module')
    def rest_config(self, env, plugins_config):
        config = RestConfig(
            plugins_config=plugins_config,
            _env_file=os.environ.get('XPUB_ENV_FILES', None)
        )
        yield config

    @pytest.fixture(scope='module')
    def rest(self, rest_config):
        yield rest_config.setup()

    @pytest.fixture(scope="module")
    def env(self, loader):
        pass

    @pytest.fixture(scope='module')
    def datasets_config(self, env):
        return {}

    @pytest.fixture(scope='module')
    def dataset_id(self):
        return 'ds'

    @pytest.fixture(scope='module')
    def client(self, env, rest):
        client = TestClient(rest.app)
        yield client

    def test_versions(self, client):
        versions_check(client)

    def test_plugins(self, client):
        plugins_check(client)

    def test_datasets(self, dataset_id, client):
        datasets_check(client, dataset_id)

    def test_html(self, dataset_id, client):
        html_check(client, dataset_id)

    def test_docs(self, client):
        docs_check(client)

    def test_zarr(self, dataset_id, client, varname):
        zarr_check(client, dataset_id, varname)

    def test_serve(self, rest_config, rest, mocker):
        serve_check(rest_config, rest, mocker)
