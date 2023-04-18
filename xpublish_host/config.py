import ipaddress as ip
import logging
import os
import typing as t
from pprint import pformat

from goodconf import GoodConf
from pydantic import (
    BaseModel,
    PositiveInt,
    PyObject,
)

import xpublish

L = logging.getLogger(__name__)


class ClusterConfig(BaseModel):
    module: PyObject
    # Plugin arguments
    args: set[str] = ()
    # Plugin named arguments
    kwargs: dict[str, t.Any] = {}


class PluginConfig(BaseModel):
    module: PyObject
    # Plugin arguments
    args: set[str] = ()
    # Plugin named arguments
    kwargs: dict[str, t.Any] = {}


class RestConfig(GoodConf):
    publish_host: ip.IPv4Address = '0.0.0.0'
    publish_port: PositiveInt = 9000
    log_level: str = 'debug'

    plugins_load_defaults: bool = True
    plugins_config: dict[str, PluginConfig] = {}

    """
    docs_url="/api"
    openapi_url="/api.json"
    """
    app_config: dict[str, t.Any] = {
        'docs_url': '/api',
        'openapi_url': '/api.json',
    }

    """
    available_bytes=1e11
    """
    cache_config: dict[str, t.Any] = {
        'available_bytes': 1e11
    }

    """
    {
        'processes': True,
        'n_workers': 8,
        'threads_per_worker': 1,
        'memory_limit': '4GiB',
    }
    {} = don't load a cluster, parallel=False must be set
    on dataset load or this will cause errors

    None = use default cluster
    """
    cluster_config: ClusterConfig | None = None

    class Config:
        file_env_file = os.environ.get('XPUB_CONFIG_FILE', 'config.yaml')
        env_file = os.environ.get('XPUB_ENV_FILES', '.env')
        env_file_encoding = 'utf-8'
        env_prefix = 'XPUB_'
        env_nested_delimiter = '__'

    def setup_rest(self):

        load_defaults = None
        if self.plugins_load_defaults is False:
            load_defaults = {}

        plugs = self.setup_plugins()

        # Start with no datasets, they are all loaded
        # using the DatasetConfigPlugin
        rest = xpublish.Rest(
            None,
            plugins=load_defaults,
            app_kws=dict(self.app_config),
            cache_kws=dict(self.cache_config),
        )
        for p in plugs.values():
            rest.register_plugin(p, overwrite=True)

        config = {
            'app': dict(self.app_config),
            'cache': dict(self.cache_config),
            'plugins': plugs,
        }
        config_out = pformat(config)
        L.info(config_out)

        return rest

    def setup_cluster(self):
        """
        Load the cluster config we should use for serving this dataset.
        Some integration with Dask Gateway here would be sweet!

        To use no cluster, set to an empty dict. To use the default, set to None.
        This is similar to how plugins work.
        """
        # None or empty - don't load a cluster
        if not self.cluster_config:
            return None

        # Only spawn a cluster if distributed is installed
        try:
            from dask.distributed import Client  # noqa
        except ImportError:
            L.warning("The dask 'distributed' library is not installed, no cluster support")
            return None

        cluster = self.cluster_config.module(
            *self.cluster_config.args,
            **self.cluster_config.kwargs
        )

        L.info(f'Created cluster: {cluster}')
        return cluster

    def setup_plugins(self):
        plugins = {}

        for p in self.plugins_config.values():
            try:
                plug = p.module(
                    *p.args,
                    **p.kwargs
                )
                plugins[plug.name] = plug
            except BaseException as e:
                L.error(f"Could not load the {p} plugin: {e}")

        return plugins

    def setup(self, create_cluster_client=True):
        """
        _summary_

        Args:
            create_cluster_client (bool, optional): When run outside of
                gunicorn this needs to be True for the dask client object
                to be created. Defaults to True.
        """
        if create_cluster_client is True:
            cluster = self.setup_cluster()
            if cluster:
                from dask.distributed import Client
                client = Client(cluster)
                L.info(f'Using cluster: {client.cluster}')
                L.info(f'Dashboard: {client.cluster.dashboard_link}')

        rest = self.setup_rest()
        return rest

    def serve_kwargs(self):
        return dict(
            host=str(self.publish_host),
            port=self.publish_port,
            log_level=self.log_level,
        )
