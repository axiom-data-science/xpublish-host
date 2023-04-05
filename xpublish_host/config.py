import ipaddress as ip
import logging
import os
import typing as t
from copy import copy
from pprint import pformat

import xpublish
from goodconf import GoodConf
from pydantic import BaseModel, PositiveInt, PyObject

logging.basicConfig(level=logging.INFO)
logging.getLogger('distributed').setLevel(logging.ERROR)
logging.getLogger('dask').setLevel(logging.ERROR)

L = logging.getLogger(__name__)


class PluginConfig(BaseModel):
    module: PyObject
    # Plugin arguments
    args: set[str] = ()
    # Plugin named arguments
    kwargs: dict[str, t.Any] = {}


class DatasetConfig(BaseModel):
    id: str
    title: str
    description: str
    loader: PyObject
    args: set[t.Any] = ()
    kwargs: dict[str, t.Any] = {}

    def load(self):
        return self.loader(*self.args, **self.kwargs)

    def serve(self, **rest_kwargs):
        """
        Helper method to run a single dataset with configs
        """
        config = RestConfig(
            datasets_config=[self],
            **rest_kwargs
        )
        rest = config.setup()
        rest.serve(
            **config.serve_kwargs()
        )


class RestConfig(GoodConf):
    publish_host: ip.IPv4Address = '0.0.0.0'
    publish_port: PositiveInt = 9000
    log_level: str = 'debug'

    datasets_config: dict[str, DatasetConfig] = {}

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
    cluster_config: dict[str, t.Any] | None = None

    class Config:
        env_file = os.environ.get('XPUB_ENV_FILES', '.env')
        env_prefix = 'XPUB_'
        env_nested_delimiter = '__'

    def setup_rest(self):

        load_defaults = None
        if self.plugins_load_defaults is False:
            load_defaults = {}

        plugs = self.setup_plugins()

        rest = xpublish.Rest(
            self.setup_datasets(),
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
        # Empty dict means don't load a cluster
        if self.cluster_config == {}:
            return None

        # Only spawn a cluster if distributed is installed
        try:
            from dask.distributed import Client, LocalCluster
        except ImportError:
            L.warning("The dask 'distributed' library is not installed, no cluster support")
            return None

        # None means load the default cluster
        cluster_config = copy(self.cluster_config)
        if cluster_config is None:
            cluster_config = {}

        default_cluster_config = dict(
            processes=True,
            n_workers=8,
            threads_per_worker=1,
            memory_limit='4GiB',
            host='0.0.0.0',
            scheduler_port=0,  # random port
            dashboard_address='0.0.0.0:0',  # random port
            worker_dashboard_address='0.0.0.0:0',  # random port
        )

        cluster_config = {
            **default_cluster_config,
            **cluster_config
        }

        cluster_info = pformat(cluster_config)
        L.info(f'Cluster: {cluster_info}')

        # Load a cluster config here and setup cluster as needed.
        cluster = LocalCluster(**cluster_config)
        client = Client(cluster)
        return client

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
                L.exception(f"Could not load the {p} plugin: {e}")

        return plugins

    def setup_datasets(self):
        datasets = {}
        for d in self.datasets_config.values():
            datasets[d.id] = d.load()
        return datasets

    def setup(self):
        _ = self.setup_cluster()
        rest = self.setup_rest()
        return rest

    def serve_kwargs(self):
        return dict(
            host=str(self.publish_host),
            port=self.publish_port,
            log_level=self.log_level,
        )


def serve(config_file: str = None):
    config = RestConfig()

    # Look for environmental variable defining the location
    # of a config file
    env_config = os.environ.get('XPUB_CONFIG_FILE', None)
    if env_config and os.path.exists(env_config):
        config.load(env_config)

    # Load in any passed in config file, or use ENV variables
    # that override any defined in the env file
    if config_file:
        config.load(config_file)

    if not env_config and not config_file:
        config.load()

    rest = config.setup()
    rest.serve(
        **config.serve_kwargs()
    )


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser("xpublish_host_serve")
    parser.add_argument("-c", "--config", default=None, help="Path to a config file", type=str)
    args = parser.parse_args()

    if args.config:
        if not os.path.exists(args.config):
            raise ValueError(f"File {args.config} not found")
        serve(config_file=args.config)
    else:
        serve()
