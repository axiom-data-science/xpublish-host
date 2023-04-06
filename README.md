# xpublish-host

A collection of tools and standards for deploying [`xpublish`](https://github.com/xarray-contrib/xpublish) instances.

## Why?

With ~50 netCDF-based datasets to be published through `xpublish`, Axiom needed a standard way to configure each of these deployments. We could have created single repository and defined each individual `xpublish` deployment, we could have created individual repositories for each dataset, or we could have done something in the middle. We decided to abstract out the parts common to each deployment and put it here into `xpublish-host`. This prevents the re-implementation of things like authentication (tbd), logging, metrics, and allows data engineers to focus on the data and not the deployment.

## Goals

* Standardize the configuration of an `xpublish` deployment (plugins, ports, cache, dask clusters, datasets, etc.) using config files and environmental variables, not python code.
* Standardize monitoring and metrics of an `xpublish` deployment,
* Provide a pre-built Docker image to run an opinionated `xpublish` deployment.

## Ideas

`xpublish-host` makes no assumptions about the datasets you want to publish through `xpublish` and only requires the path to an importable python function that returns the object you want to be passed in as an argument to `xpublish.Rest`. This will allow `xpublish-host` to support datasets in addition to `xarray.Dataset` in the future, such as Parquet files.

We maintain an `xpublish-inventory` repository that defines YAML configurations and python functions for each `xpublish` dataset we want to publish. Those YAML configurations and python functions are installed as library into the `xpublish-host` container on deployment. There are better ways to do this (auto-discovery) but you have to start somewhere.

## Installation

Most users will not need to install `xpublish_host` directly as a library but instead will use the Docker image to deploy an `xpublish` instance. If you want to use the `xpublish_host` tools and config objects directly in python code, you can of course install it:

For `conda` users you can

```shell
conda install --channel conda-forge xpublish_host
```

or, if you are a `pip` user

```shell
pip install xpublish_host
```

## Usage

### Configuration

The configuration is managed using `Pydantic` [BaseSettings](https://docs.pydantic.dev/usage/settings/) and [GoodConf](https://github.com/lincolnloop/goodconf/) for loading configuration from files.

The `xpublish_host` configuration can be set in a few ways

* **Environmental variables** - prefixed with `XPUB_`, they map directly to the `pydantic` settings classes,
* **Environment files** - Load environmental variables from a file. Uses `XPUB_ENV_FILES` to control the location of this file if it is defined. See the [`Pydantic` docs](https://docs.pydantic.dev/usage/settings/#dotenv-env-support) for more information,
* **Configuration files (JSON and YAML)** - [`GoodConf` based](https://github.com/lincolnloop/goodconf) configuration files. When using the `xpublish_host.config.serve` helper this file can be set by defining `XPUB_CONFIG_FILE`.
* **Python arguments (API only)** - When using `xpublish-host` as a library you can use the args/kwargs of each configuration object to control your `xpublish` instance.

There are three Settings classes:

* `PluginConfig` - configure `xpublish` plugins,
* `DatasetConfig` - configure the datasets available to `xpublish`,
* `RestConfig` - configure how the `xpublish` instance is run, including the `PluginConfig` and `DatasetConfig`.

The best way to get familiar with which configuration options are available (until the documentation catches up) is to look at the actually configuration classes in `xpublish_host/config.py` and the tests in `tests/test_config.py`.

A feature-full configuration is as follows, which includes the defaults for each field.

```yaml
# These are passed into the `xpublish.Rest.serve` method to control how the
# server is run
publish_host: "0.0.0.0"
publish_port: 9000
log_level: debug

# Dask cluster configuration. Current uses a LocalCluster.
# The keyword arguments are passed directly into `dask.distributed.LocalCluster`
# Omitting cluster_config or setting to null will load the defaults.
# Settings cluster_config to an empty dict will avoid using a dask cluster.
cluster_config:
  processes: true
  n_workers: 8
  threads_per_worker: 1
  memory_limit: 4GiB
  host: "0.0.0.0"
  scheduler_port: 0  # random port
  dashboard_address: 0.0.0.0:0  # random port
  worker_dashboard_address: 0.0.0.0:0  # random port

# Should xpublish discover and load plugins?
plugins_load_defaults: true

# Define any additional plugins. This is where you can override
# default plugins. These will replace any auto-discovered plugins.
# The keys here (pc1) are not important and are not used internally
plugins_config:
  pc1:
    module: xpublish.plugins.included.zarr.ZarrPlugin
      kwargs:
        dataset_router_prefix: /zarr

# Keyword arguments to pass into `xpublish.Rest` as app_kws
# i.e. xpublish.Rest(..., app_kws=app_config)
app_config:
  docs_url: /api
  openapi_url: /api.json

# Keyword arguments to pass into `xpublish.Rest` as cache_kws
# i.e. xpublish.Rest(..., cache_kws=cache_config)
cache_config:
  available_bytes: 1e11

# Define all of the datasets to load into the xpublish instance.
# The keys here (dc1) are not important and are not used internally
datasets_config:
  dc1:
    # The ID is used as the "key" of the dataset in `xpublish.Rest`
    # i.e. xpublish.Rest({ [dataset.id]: [loader_function_return] })
    id: dataset_id
    title: Dataset Title
    description: Dataset Description
    # Path to an importable python function that returns the dataset you want
    # to pass into `xpublish.Rest`
    loader: [python module path]
    # Arguments passed into the `loader` function
    args:
      - [loader arg1]
      - [loader arg2]
    # Keyword arguments passed into the `loader` function. See the `examples`
    # directory for more details on how this can be used.
    kwargs:
      t_axis: 'time'
      y_axis: 'lat'
      x_axis: 'lon'
      open_kwargs:
        parallel: false
```

### API

To deploy an `xpublish` instance while pulling settings from a yaml file and environmental variables you can use the `serve` function. This is what is used under the hood in the Docker image.

```python
from xpublish_host.config import serve

serve('config.yaml')

os.environ['XPUB_ENV_FILES'] = '/home/user/.env'
serve()

os.environ['XPUB_CONFIG_FILE'] = 'config.yaml'
serve()
```

You can also use the `RestConfig` and `DatasetConfig` objects directly to serve datasets

#### `RestConfig`

```python
from xpublish_host.config import RestConfig

dc = DatasetConfig(
    id='id',
    title='title',
    description='description',
    loader='[python function path]',
)

rc = RestConfig(datasets_config={'ds': dc})
rc.load('[config_file]')  # optionally load a configuration file
rest = rc.setup()  # This returns an `xpublish.Rest` instance
rest.serve(
    host='0.0.0.0',
    port=9000,
    log_level='debug',
)
```

#### `DatsetConfig`

```python
from xpublish_host.config import DatasetConfig

dc = DatasetConfig(
    id='id',
    title='title',
    description='description',
    loader='[python function path]',
)

# Keyword arguments are passed into RestConfig and can include all of the
# top level configuration options.
dc.serve()
```

### CLI

There is a CLI command you can use to run an `xpublish` server and optionally pass in the path to a configuration file:

```shell
# Pass in a config file
python xpublish_host/config.py -c xpublish_host/examples/example.yaml

# Use ENV variables
XPUB_CONFIG_FILE=xpublish_host/examples/example.yaml python xpublish_host/config.py
```

Either way, `xpublish` will be running on port 9000 with (2) datasets: `simple` and `kwargs`. You can access the instance at `http://[host]:9000/datasets/`.

### Docker

The Docker image by default loads a configuration file from `/xpd/config.yaml` and an environmental variable file from `/xpd/.env`. You can change the location of those files by setting the env variables `XPUB_CONFIG_FILE` and `XPUB_ENV_FILES` respectively.

```shell
# Using default config path
docker run --rm -p 9000:9000 -v "$(pwd)/xpublish_host/examples/example.yaml:/xpd/config.yaml" axiom/xpublish-host:latest

# Using ENV variables
docker run --rm -p 9000:9000 -e "XPUB_CONFIG_FILE=/xpd/xpublish_host/examples/example.yaml" axiom/xpublish-host:latest
```

Either way, `xpublish` will be running on port 9000 with (2) datasets: `simple` and `kwargs`. You can access the instance at `http://[host]:9000/datasets/`.
