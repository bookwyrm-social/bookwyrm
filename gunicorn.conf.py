import multiprocessing
from environs import Env

env = Env()
env.read_env()

bind = "0.0.0.0:8000"
# clip worker count to be between 1 and 12
#  https://gunicorn.org/design/?h=worker#how-many-workers
workers = min([multiprocessing.cpu_count() * 2 + 1, 12])
if env.bool("DEBUG", False):
    reload = True
