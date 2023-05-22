# xpublish-host

A collection of tools and standards for deploying [`xpublish`](https://github.com/xarray-contrib/xpublish) instances.

## Why?

With ~50 netCDF-based datasets to be published through `xpublish`, Axiom needed a standard way to configure each of these deployments. We could have created single repository and defined each individual `xpublish` deployment, we could have created individual repositories for each dataset, or we could have done something in the middle. We decided to abstract out the parts common to each deployment and put it here into `xpublish-host`. This prevents the re-implementation of things like authentication (tbd), logging, metrics, and allows data engineers to focus on the data and not the deployment.

## Goals

* Standardize the configuration of an `xpublish` deployment (plugins, ports, cache, dask clusters, etc.) using config files and environmental variables, not python code.
* Standardize on a core set of `FastAPI` observability middleware (metrics, monitoring, etc.),
* Provide a plugin to define `xpublish` datasets via configuration (`DatasetsConfigPlugin`).
* Provide a set of common `loader` functions for use as an argument in a `DatasetsConfig` to standardize common access patterns (`xarray.open_mfdataset` is currently supported).
* Provide a pre-built Docker image to run an opinionated and performant `xpublish` instance using `gunicorn`.

## Thoughts

`xpublish-host` makes no assumptions about the datasets you want to publish through `xpublish` and only requires the path to an importable python function that returns the object you want to be passed in as an argument to `xpublish.Rest`. This allows `xpublish-host` to support datasets in addition to `xarray.Dataset` in the future, such as Parquet files.

As a compliment to `xpublish-host`, Axiom maintain a private repository of server and dataset YAML files that are compatible with `xpublish-host` and the `DatasetsConfigPlugin`. On deploy we mount these files into the `xpublish-host` container and they represent the only customizations required to get a working `xpublish-host` instance going.

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

or, if you are using `docker`

```shell
docker run --rm -p 9000:9000 axiom/xpublish-host:latest
```

## Batteries Included

### Host Configuration

A top-level configuration for running an `xpublish-host` instance.

The configuration is managed using `Pydantic` [BaseSettings](https://docs.pydantic.dev/usage/settings/) and [GoodConf](https://github.com/lincolnloop/goodconf/) for loading configuration from files.

The `xpublish-host` configuration can be set in a few ways

* **Environmental variables** - prefixed with `XPUB_`, they map directly to the `pydantic` settings classes,
* **Environment files** - Load environmental variables from a file. Uses `XPUB_ENV_FILES` to control the location of this file if it is defined. See the [`Pydantic` docs](https://docs.pydantic.dev/usage/settings/#dotenv-env-support) for more information,
* **Configuration files (JSON and YAML)** - [`GoodConf` based](https://github.com/lincolnloop/goodconf) configuration files. When using the `xpublish_host.app.serve` helper this file can be set by defining `XPUB_CONFIG_FILE`.
* **Python arguments (API only)** - When using `xpublish-host` as a library you can use the args/kwargs of each configuration object to control your `xpublish` instance.

The best way to get familiar with which configuration options are available (until the documentation catches up) is to look at the actually configuration classes in `xpublish_host/config.py` and the tests in `tests/test_config.py` and `tests/utils.py`

A feature-full configuration is as follows, which includes the defaults for each field.

```yaml
# These are passed into the `xpublish.Rest.serve` method to control how the
# server is run. These are ignored if running through `gunicorn` in production mode
# or using the Docker image. See the `CLI` section below for more details.
publish_host: "0.0.0.0"
publish_port: 9000
log_level: debug

# Dask cluster configuration.
# The `args` and `kwargs` arguments are passed directly into the `module`
# Omitting cluster_config or setting to null will not use a cluster.
cluster_config:
  module: dask.distributed.LocalCluster
  args: []
  kwargs:
    processes: true
    n_workers: 2
    threads_per_worker: 1
    memory_limit: 1GiB
    host: "0.0.0.0"
    scheduler_port: 0  # random port
    dashboard_address: 0.0.0.0:0  # random port
    worker_dashboard_address: 0.0.0.0:0  # random port

# Should xpublish discover and load plugins?
plugins_load_defaults: true

# Define any additional plugins. This is where you can override
# default plugins. These will replace any auto-discovered plugins.
# The keys here (zarr, dconfig) are not important and are not used internally
plugins_config:

  zarr:
    module: xpublish.plugins.included.zarr.ZarrPlugin

  dconfig:
    module: xpublish_host.plugins.DatasetsConfigPlugin
    kwargs:
      # Define all of the datasets to load into the xpublish instance.
      datasets_config_file: datasets.yaml
      datasets_config:
        # The keys here (dataset_id_1) are not important and are not used internally
        # but it is good practice to make them equal to the dataset's id field
        dataset_id_1:
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
            keyword1: 'keyword1'
            keyword2: false
          # After N seconds, invalidate the dataset and call the `loader` method again
          invalidate_after: 10
          # If true, defers the initial loading of the dataset until the first request
          # for the dataset comes in. Speeds up server load times but slows down the
          # first request (per-process) to each dataset
          skip_initial_load: true

# Keyword arguments to pass into `xpublish.Rest` as app_kws
# i.e. xpublish.Rest(..., app_kws=app_config)
app_config:
  docs_url: /api
  openapi_url: /api.json

# Keyword arguments to pass into `xpublish.Rest` as cache_kws
# i.e. xpublish.Rest(..., cache_kws=cache_config)
cache_config:
  available_bytes: 1e11
```

### Metrics

`xpublish-host` provides a [prometheus](https://prometheus.io/) compatible metrics endpoint. The docker image supports multi-process metric generation through `gunicorn`. By default the metrics endpoint is available at `/metrics`.

The default labels format `xpublish-host` metrics are:

```json
[XPUB_METRICS_PREFIX_NAME]_[metric_name]{app_name="[XPUB_METRICS_APP_NAME]",environment="[XPUB_METRICS_ENVIRONMENT]"}
```

The metrics endpoint can be configured using environmental variables:

* `XPUB_METRICS_APP_NAME` (default: `xpublish`)
* `XPUB_METRICS_PREFIX_NAME` (default: `xpublish_host`)
* `XPUB_METRICS_ENDPOINT` (default: `/metrics`)
* `XPUB_METRICS_ENVIRONMENT` (default: `development`)
* `XPUB_METRICS_DISABLE` - disabled the metrics endpoint by setting this to any value

### Health

A health check endpoint is available at `/health` to be used by various health checkers (docker, load balancers, etc.). You can disable the heath check endpoint by settings the environmental variable `XPUB_HEALTH_DISABLE` to any value. To change the endpoint, set `XPUB_HEALTH_ENDPOINT` to the new value, i.e. `export XPUB_HEALTH_ENDPOINT="/amiworking"`

### DatasetsConfigPlugin

This plugin is designed to load datasets into `xpublish` from a mapping of `DatatsetConfig` objects. It can get the mapping directory from the plugin arguments or from a `yaml` file.

The `DatasetsConfigPlugin` plugin can take two parameters:

* `datasets_config: dict[str, DatasetConfig]`
* `datasets_config_file: Path` - File path to a YAML file defining the above `datasets_config` object.

Define datasets from an `xpublish-host` configuration file:

```yaml
plugins_config:
  dconfig:
    module: xpublish_host.plugins.DatasetsConfigPlugin
    kwargs:
      datasets_config:
        simple:
          id: static
          title: Static
          description: Static dataset that is never reloaded
          loader: xpublish_host.examples.datasets.simple
```

Or from a `xpublish-host` configuration file referencing an external datasets configuration file

```yaml
# datasets.yaml
datasets_config:
  simple:
    id: static
    title: Static
    description: Static dataset that is never reloaded
    loader: xpublish_host.examples.datasets.simple
```

```yaml
plugins_config:
  dconfig:
    module: xpublish_host.plugins.DatasetsConfigPlugin
    kwargs:
      datasets_config_file: datasets.yaml
```

You can also mix and match between in-line configurations and file-based dataset configurations. Always be sure the `id` field is unique for each defined dataset or they will overwrite each other, with config file definitions taking precedence.

```yaml
plugins_config:
  dconfig:
    module: xpublish_host.plugins.DatasetsConfigPlugin
    kwargs:
      datasets_config_file: datasets.yaml
      datasets_config:
        simple_again:
          id: simple_again
          title: Simple
          description: Simple Dataset
          loader: xpublish_host.examples.datasets.simple
```

#### DatasetConfig

The `DatasetConfig` object is a way to store information about how to load a dataset you want published through `xpublish`. It supports dynamically loading datasets on request rather than requiring them to be loaded when `xpublish` is started. It allows mixing together static datasets that do not change and dynamic datasets that you may want to reload periodically onto one `xpublish` instance.

The `loader` parameter should be a path to a python module that will return the dataset you want served through `xpublish`. The `args` and `kwargs` parameters are passed into that function when `xpublish` needs to load or reload your dataset.

Here is an example of how to configure an `xpublish` instance that will serve a `static` dataset that is loaded once on server start and a `dynamic` dataset that is not reloaded on server start. It is loaded for the first time on first request and then reloaded every 10 seconds. It isn't reloaded on a schedule, it is reloaded on-request if the dataset has not been accessed after `invalidate_after` seconds has elapsed.

```yaml
datasets_config:

  simple:
    id: static
    title: Static
    description: Static dataset that is never reloaded
    loader: xpublish_host.examples.datasets.simple

  dynamic:
    id: dynamic
    title: Dynamic
    description: Dynamic dataset re-loaded on request periodically
    loader: xpublish_host.examples.datasets.simple
    skip_initial_load: true
    invalidate_after: 10
```

You can run the above config file and take a look at what is produced. There are (2) datasets: `static` and `dynamic`. If you watch the logs and keep refreshing access to the `dynamic` dataset, it will re-load the dataset every `10` seconds.

```shell
$ xpublish-host -c xpublish_host/examples/dynamic.yaml

INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)
INFO:     127.0.0.1:42808 - "GET /datasets HTTP/1.1" 200 OK
# The static dataset is already loaded
INFO:     127.0.0.1:41938 - "GET /datasets/static/ HTTP/1.1" 200 OK
# The dynamic dataset is loaded on first access
INFO:xpublish_host.plugins:Loading dataset: dynamic
INFO:     127.0.0.1:41938 - "GET /datasets/dynamic/ HTTP/1.1" 200 OK
# Subsequent access to dynamic before [invalidate_after] seconds uses
# the already loaded dataset
INFO:     127.0.0.1:41938 - "GET /datasets/dynamic/ HTTP/1.1" 200 OK
INFO:     127.0.0.1:41938 - "GET /datasets/dynamic/ HTTP/1.1" 200 OK
INFO:     127.0.0.1:41938 - "GET /datasets/dynamic/ HTTP/1.1" 200 OK
INFO:     127.0.0.1:41938 - "GET /datasets/dynamic/ HTTP/1.1" 200 OK
INFO:     127.0.0.1:41938 - "GET /datasets/dynamic/ HTTP/1.1" 200 OK
# Eventually [invalidate_after] seconds elapses and the dynamic
# dataset is reloaded when the request is made
INFO:xpublish_host.plugins:Loading dataset: dynamic
INFO:     127.0.0.1:41938 - "GET /datasets/dynamic/ HTTP/1.1" 200 OK
INFO:     127.0.0.1:41938 - "GET /datasets/dynamic/ HTTP/1.1" 200 OK
# The static dataset is never reloaded
INFO:     127.0.0.1:41938 - "GET /datasets/static/ HTTP/1.1" 200 OK
# This works when accessing datasets through other plugins as well (i.e. ZarrPlugin)
INFO:xpublish_host.plugins:Loading dataset: dynamic
INFO:     127.0.0.1:48092 - "GET /datasets/dynamic/zarr/.zmetadata HTTP/1.1" 200 OK
INFO:     127.0.0.1:48092 - "GET /datasets/dynamic/zarr/.zmetadata HTTP/1.1" 200 OK
```

### Loaders

#### `xpublish_host.loaders.mfdataset.load_mfdataset`

A loader function to utilize `xarray.open_mfdataset` to open a path of netCDF files. Common loading patterns have been abstracted into keyword arguments to standardize the function as much as possible.

```python
def load_mfdataset(
    root_path: str | Path,  # root folder path
    file_glob: str,  # a file glob to load
    open_mfdataset_kwargs: t.Dict = {},  #  any kwargs to pass directly to xarray.open_mfdataset
    file_limit: int | None = None,  # limit the number of files to load, from the end after sorting ASC
    skip_head_files: int | None = 0,  # skip this number of files from the beginning of the file list
    skip_tail_files: int | None = 0,  # skip this number of files from the end of the file list
    computes: list[str] | None = None,  # A list of variable names to call .compute() on to they are evaluated (useful for coordinates)
    chunks: dict[str, int] | None = None,  # A dictionary of chunks to use for the dataset
    axes: dict[str, str] | None = None,  # A dictionary of axes mapping using the keys t, x, y, and z
    sort_by: dict[str, str] | None = None,  # The field to sort the resulting dataset by (usually the time axis)
    isel: dict[str, slice] | None = None,  # a list of isel slices to take after loading the dataset
    sel: dict[str, slice] | None = None,  # a list of sel slices to take after loading the dataset
    rechunk: bool = False,  # if we should re-chunk the data applying all sorting and slicing
    attrs_file_idx: int = -1,  # the index into the file list to extract metadata from
    combine_by_coords: list[str | Path] = None,  # a list of files to combine_by_coords with, useful for adding in grid definitions
    **kwargs
) -> xr.Dataset:
```

Yeah, that is a lot. An Example may be better.

```yaml
# Select the last 24 indexes of ocean_time and the first Depth index
# from the last 5 netCDF files found in a directory,
# after sorting by the filename. Drop un-needed variables
# and use a Dask cluster to load the files if one is available.
# Compute the h and mask variables into memory so they are
# not dask arrays, and finally, sort the resulting xarray
# dataset by ocean_time and then Depth.
datasets_config:
  sfbofs_latest:
    id: sfbofs_latest
    title: Last 24 hours of SFBOFS surface data
    description: Last 24 hours of SFBOFS surface data
    loader: xpublish_host.loaders.mfdataset.load_mfdataset
    kwargs:
      root_path: data/sfbofs/
      file_glob: "**/*.nc"
      file_limit: 5
      axes:
        t: ocean_time
        z: Depth
        x: Longitude
        y: Latitude
      computes:
        - h
        - mask
      chunks:
        ocean_time: 24
        Depth: 1
        nx: 277
        ny: 165
      sort_by:
        - ocean_time
        - Depth
      isel:
        Depth: [0, 1, null]
        ocean_time: [-24, null, null]
      open_mfdataset_kwargs:
        parallel: true
        drop_variables:
          - forecast_reference_time
          - forecast_hour
```

## Running

There are two main ways to run `xpublish-host`, one is suited for Development (`xpublish` by default uses `uvicorn.run`) and one suited for Production (`xpublish-host` uses `gunicorn`). See the [`Uvicorn` docs](https://www.uvicorn.org/deployment/) for more information.

### Development

#### API

To configure and deploy an `xpublish` instance while pulling settings from a yaml file and environmental variables you can use the `serve` function.

Load config from a file

```python
>>> from xpublish_host.app import serve
>>> serve('xpublish_host/examples/example.yaml')

INFO:goodconf:Loading config from xpublish_host/examples/example.yaml
...
INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)python
```

Load environmental variables from a custom .env file
```python
>>> import os
>>> os.environ['XPUB_ENV_FILES'] = 'xpublish_host/examples/example.env'
>>> from xpublish_host.app import serve
>>> serve()

INFO:goodconf:No config file specified. Loading with environment variables.
...
INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)python
```

Set the default location to load a configuration file from
```python
>>> import os
>>> os.environ['XPUB_CONFIG_FILE'] = 'xpublish_host/examples/example.yaml'
>>> from xpublish_host.app import serve
>>> serve()

INFO:goodconf:Loading config from xpublish_host/examples/example.yaml
...
INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)python
```

##### `RestConfig`

You can also use the `RestConfig` objects directly to serve datasets through the API while mixing in configuration file as needed. If you using the API in this way without using a config file or environmental variables it is better to use the `xpublish` API directly instead.

```python
from xpublish_host.config import RestConfig, PluginConfig
from xpublish_host.plugins import DatasetsConfigPlugin

pc = PluginConfig(
    module=DatasetsConfigPlugin,
    kwargs=dict(
        datasets_config=dict(
            simple=dict(
                id='simple',
                title='title',
                description='description',
                loader='xpublish_host.examples.datasets.simple',
            ),
            kwargs=dict(
                id='kwargs',
                title='title',
                description='description',
                loader='xpublish_host.examples.datasets.kwargs',
                args=('temperature',),
                kwargs=dict(
                  values=[0, 1, 2, 3, 4, 5, 6, 7, 8]
                )
            )
        )
    )
)

rc = RestConfig(
    load=True,
    plugins_config={
        'dconfig': pc
    }
)

rest = rc.setup()  # This returns an `xpublish.Rest` instance
rest.serve(
    host='0.0.0.0',
    port=9000,
    log_level='debug',
)
```

##### `DatasetConfig`

If you are serving a single dataset there is a helper method `serve` on the `DatasetConfig` object.

```python
from xpublish_host.plugins import DatasetConfig
dc = DatasetConfig(
    id='id',
    title='title',
    description='description',
    loader='xpublish_host.examples.datasets.simple',
)

# Keyword arguments are passed into RestConfig and can include all of the
# top level configuration options.
dc.serve(
    host='0.0.0.0',
    port=9000,
    log_level='debug',
)
```

#### CLI (dev)

When developing locally or in a non-production environment you can use helper CLI methods to run an `xpublish` server and optionally pass in the path to a configuration file. Use the provided `xpublish-host` command (when installed through `setuptools`) or `python xpublish_host/app.py`, they are the same thing!

Pass in a config file argument

```shell
$ xpublish-host -c xpublish_host/examples/example.yaml

INFO:goodconf:Loading config from xpublish_host/examples/example.yaml
...
INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)
```

Pull config file from an environmental variable

```shell
$ XPUB_CONFIG_FILE=xpublish_host/examples/example.yaml xpublish-host

INFO:goodconf:Loading config from xpublish_host/examples/example.yaml
...
INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)
```

Either way, `xpublish` will be running on port 9000 with (2) datasets: `simple` and `kwargs`. You can access the instance at `http://[host]:9000/datasets/`.

### Production

To get `xpublish` to play nicely with async loops and processes being run by `gunicorn` and `dask`, there is a custom worker class (`xpublish_host.app.XpdWorker`) and a `gunicorn` config file (`xpublish_host/gunicorn.conf.py`) that must be used. These are loaded automatically if you are using the provided Docker image.

If you define a `cluster_config` object when running using `gunicorn`, one cluster is spun up in the parent process and the scheduler_address for that cluster is passed to each  worker process. If you really want one cluster per process, you will have to implement it yourself and send a PR ;). Better integration with `LocalCluster` would be nice, but the way it is done now allows a "bring your own" cluster configuration as well if you are managing `dask` clusters outside of the scope of this project.

**Note:** when using `gunicorn` the host and port configurations can only be passed in using the `-b/--bind` arguments or in the configuration file. If set in any environmental variables they will be ignored!

#### CLI (prod)

You can run `gunicorn` manually (locally) to test how things will run inside of the Docker image.

```shell
XPUB_CONFIG_FILE=xpublish_host/examples/example.yaml gunicorn xpublish_host.app:app -c xpublish_host/gunicorn.conf.py
```

If you would like the metrics endpoint (`/metrics`) to function correctly when running through `gunicorn`, you need to create a temporary directory for metrics and pass it in as the `PROMETHEUS_MULTIPROC_DIR` directory. This is handled automatically in the provided Docker image.

```shell
mkdir -p /tmp/xpub_metrics
PROMETHEUS_MULTIPROC_DIR=/tmp/xpub_metrics XPUB_CONFIG_FILE=xpublish_host/examples/example.yaml gunicorn xpublish_host.app:app -c xpublish_host/gunicorn.conf.py
```

Either way, `xpublish` will be running on port 9000 with (2) datasets: `simple` and `kwargs`. You can access the instance at `http://[host]:9000/datasets/`. Metrics are available at `http://[host]:9000/metrics`

##### Docker

The Docker image by default loads an `xpublish-host` configuration file from `/xpd/config.yaml`, a datasets configuration object from `/xpd/datasets.yaml`, and an environmental variable file from `/xpd/.env`. You can change the location of those files by setting the env variables `XPUB_CONFIG_FILE`, `XPUBDC_CONFIG_FILE`, and `XPUB_ENV_FILES` respectively.

```shell
# Using default config path
docker run --rm -p 9000:9000 -v "$(pwd)/xpublish_host/examples/example.yaml:/xpd/config.yaml" axiom/xpublish-host:latest

# Using ENV variables
docker run --rm -p 9000:9000 -e "XPUB_CONFIG_FILE=/xpd/xpublish_host/examples/example.yaml" axiom/xpublish-host:latest
```

Either way, `xpublish` will be running on port 9000 with (2) datasets: `simple` and `kwargs`. You can access the instance at `http://[host]:9000/datasets/`.
