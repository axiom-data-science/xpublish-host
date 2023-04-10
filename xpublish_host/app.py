import logging
import os

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
    if os.environ.get("XPUB_DISABLE_HEALTH"):
        return

    app.add_route("/health", health_check)
    return


def setup_metrics(app):

    if os.environ.get("XPUB_DISABLE_METRICS"):
        return

    envvar = 'PROMETHEUS_MULTIPROC_DIR'
    if envvar not in os.environ:
        L.warning(f"{envvar} is not set! Metrics will not work if using gunicorn.")

    try:
        from starlette_exporter import PrometheusMiddleware, handle_metrics
        from starlette_exporter.optional_metrics import request_body_size, response_body_size

        app.add_middleware(
            PrometheusMiddleware,
            app_name='xpublish_host',
            prefix='xpub',
            buckets=[0.01, 0.1, 0.25, 0.5, 1.0],
            skip_paths=['/health', '/metrics', '/favicon.ico'],
            group_paths=False,
            optional_metrics=[response_body_size, request_body_size]
        )
        app.add_route("/metrics", handle_metrics)
    except BaseException:
        raise


def setup_config(config_file: str = None, **setup_kwargs):
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

    return config


def setup_xpublish(config: RestConfig = None, **setup_kwargs):
    rest = config.setup(**setup_kwargs)
    app = rest.app
    _ = setup_metrics(app)
    _ = setup_health(app)
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


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser("xpublish_host_serve")
    parser.add_argument("-c", "--config", default=None, help="Path to a config file", type=str)
    args = parser.parse_args()

    if args.config and not os.path.exists(args.config):
        raise ValueError(f"File {args.config} not found")
    serve(config_file=args.config)
