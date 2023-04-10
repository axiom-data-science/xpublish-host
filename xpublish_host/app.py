import os

from uvicorn.workers import UvicornWorker

from xpublish_host.config import RestConfig


class XpdWorker(UvicornWorker):
    CONFIG_KWARGS = {
        "factory": True,
    }


def setup_xpublish(config_file: str = None):
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
    return rest, config


def serve(config_file: str = None):
    rest, config = setup_xpublish(config_file)
    rest.serve(
        **config.serve_kwargs()
    )


def app():
    rest, _ = setup_xpublish()
    return rest.app


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser("xpublish_host_serve")
    parser.add_argument("-c", "--config", default=None, help="Path to a config file", type=str)
    args = parser.parse_args()

    if args.config and not os.path.exists(args.config):
        raise ValueError(f"File {args.config} not found")
    serve(config_file=args.config)
