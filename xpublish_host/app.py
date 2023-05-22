import logging
import os
import re

from fastapi import status
from fastapi.responses import JSONResponse
from uvicorn.workers import UvicornWorker

from xpublish_host.config import RestConfig

logging.basicConfig(level=logging.INFO)
logging.getLogger('distributed').setLevel(logging.ERROR)
logging.getLogger('dask').setLevel(logging.ERROR)

L = logging.getLogger(__name__)


class XpdWorker(UvicornWorker):
    CONFIG_KWARGS = {
        "factory": True,
    }


def health_check(request):
    return JSONResponse(
        {'xpublish': 'online'},
        status_code=status.HTTP_200_OK,
        media_type="application/health+json",
    )


def setup_health(app):
    if os.environ.get("XPUB_HEALTH_DISABLE"):
        return

    health = os.environ.get("XPUB_HEALTH_ENDPOINT", "/health")

    app.add_route(health, health_check)
    return health


def get_dataset_label(request):
    try:
        pattern = r'^.*\/datasets\/(\w+)\/.*$'
        return re.match(pattern, str(request.url)).group(1)
    except BaseException:
        return ''


def setup_metrics(app, health_endpoint):

    if os.environ.get("XPUB_METRICS_DISABLE"):
        return

    envvar = 'PROMETHEUS_MULTIPROC_DIR'
    if envvar not in os.environ:
        L.warning(f"{envvar} is not set! Metrics will not work if using gunicorn.")

    app_name = os.environ.get("XPUB_METRICS_APP_NAME", "xpublish")
    prefix_name = os.environ.get("XPUB_METRICS_PREFIX_NAME", "xpublish_host")
    environment = os.environ.get("XPUB_METRICS_ENVIRONMENT", "development")
    metrics = os.environ.get("XPUB_METRICS_ENDPOINT", "/metrics")

    try:
        from starlette_exporter import PrometheusMiddleware, handle_metrics
        from starlette_exporter.optional_metrics import request_body_size, response_body_size

        app.add_middleware(
            PrometheusMiddleware,
            app_name=app_name,
            prefix=prefix_name,
            buckets=[0.01, 0.1, 0.25, 0.5, 1.0],
            skip_paths=[health_endpoint, metrics, '/favicon.ico'],
            group_paths=False,
            optional_metrics=[response_body_size, request_body_size],
            labels=dict(
                environment=environment,
                dataset=get_dataset_label,
            )
        )
        app.add_route(metrics, handle_metrics)
    except BaseException:
        raise


# def setup_config(config_file: str = None, **setup_kwargs):
#     env_config = os.environ.get('XPUB_ENV_FILES', None)

#     # Load in any passed in config file, or use ENV variables
#     # that override any defined in the env file
#     if config_file:
#         config = RestConfig(_env_file=env_config, load=False)
#         config.load(config_file)
#         return config

#     # Look for environmental variable defining the location of a config file
#     config_file = os.environ.get('XPUB_CONFIG_FILE', None)
#     if config_file and os.path.exists(config_file):
#         config = RestConfig(_env_file=env_config, load=False)
#         config.load(config_file)
#         return config

#     return RestConfig(_env_file=env_config)


def setup_config(config_file: str = None, **setup_kwargs):
    env_config = os.environ.get('XPUB_ENV_FILES', None)
    config = RestConfig(_env_file=env_config)

    # Look for environmental variable defining the location
    # of a config file
    yaml_config = os.environ.get('XPUB_CONFIG_FILE', None)
    if yaml_config and os.path.exists(yaml_config):
        config.load(yaml_config)

    # Load in any passed in config file, or use ENV variables
    # that override any defined in the env file
    if config_file:
        config.load(config_file)

    if not yaml_config and not config_file:
        config.load()

    return config


def setup_xpublish(config: RestConfig = None, **setup_kwargs):
    rest = config.setup(**setup_kwargs)
    app = rest.app
    health_endpoint = setup_health(app)
    _ = setup_metrics(app, health_endpoint)
    rest._app = app

    return rest, config


def serve(config_file: str = None):
    config = setup_config(config_file)
    rest, config = setup_xpublish(config)
    rest.serve(
        **config.serve_kwargs()
    )


def app():
    config = setup_config()
    rest, _ = setup_xpublish(config, create_cluster_client=False)
    return rest.app


def run():
    import argparse
    parser = argparse.ArgumentParser("xpublish_host_serve")
    parser.add_argument("-c", "--config", default=None, help="Path to a config file", type=str)
    args = parser.parse_args()

    if args.config and not os.path.exists(args.config):
        raise ValueError(f"File {args.config} not found")
    serve(config_file=args.config)


if __name__ == '__main__':
    run()
