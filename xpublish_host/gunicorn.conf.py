from prometheus_client import multiprocess

proc_name = 'xpublish'
bind = "0.0.0.0:9000"
workers = 4
threads = 1
worker_class = 'xpublish_host.app.XpdWorker'
accesslog = '-'
errorlog = '-'
loglevel = 'info'
capture_output = True
preload_app = True
timeout = 0
keepalive = 10
graceful_timeout = 10


def child_exit(server, worker):
    try:
        multiprocess.mark_process_dead(worker.pid)
    except TypeError:
        pass


def on_starting(server):
    """
    Create a dask cluster object as needed and store the
    scheduler address for later usage in the worker process
    init
    """
    from xpublish_host.app import setup_config
    config = setup_config()
    cluster = config.setup_cluster()
    if hasattr(cluster, 'scheduler_address'):
        server.XPUB_DASK_SCHEDULER_ADDRESS = cluster.scheduler_address


def post_fork(server, worker):
    """
    In each worker, connect to the scheduler address of the dask cluster
    that has already been configured.
    """
    if hasattr(server, 'XPUB_DASK_SCHEDULER_ADDRESS'):
        from dask.distributed import Client
        client = Client(server.XPUB_DASK_SCHEDULER_ADDRESS)
        print(f'Worker {worker.pid} is using cluster: {client} at {client.dashboard_link}')
