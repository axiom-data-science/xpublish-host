import os

APP_NAME = os.environ.get("XPUB_METRICS_APP_NAME", "xpublish")
PREFIX_NAME = os.environ.get("XPUB_METRICS_PREFIX_NAME", "xpublish_host")
ENVIRONMENT = os.environ.get("XPUB_METRICS_ENVIRONMENT", "development")

DEFAULT_LABELS = {
    'environment': ENVIRONMENT,
    'app_name': APP_NAME,
}


def create_metric(metric_type, name, description, labels, *args, **kwargs):
    labels += list(DEFAULT_LABELS.keys())
    return metric_type(
        f"{PREFIX_NAME}_{name}",
        description,
        labels,
        *args,
        **kwargs
    )
