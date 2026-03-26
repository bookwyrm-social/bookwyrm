import multiprocessing
from environs import Env

env = Env()
env.read_env()

bind = "0.0.0.0:8000"
workers = 2
threads = min([multiprocessing.cpu_count(), 12])
max_requests = 1000
max_requests_jitter = 100
worker_class = "gthread"
if env.bool("DEBUG", False):
    reload = True
