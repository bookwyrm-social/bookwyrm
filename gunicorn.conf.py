import multiprocessing
from environs import Env

env = Env()
env.read_env()

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
if env.bool("DEBUG", False):
    reload = True
