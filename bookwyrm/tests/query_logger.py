""" Log query runtimes for testing """
import time
from environs import Env

env = Env()
env.read_env()
MAX_QUERY_DURATION = float(env("MAX_QUERY_DURATION"))


class QueryLogger:
    """Returns the sql and duration for any query run
    Taken wholesale from:
    https://docs.djangoproject.com/en/dev/topics/db/instrumentation/
    """

    def __init__(self):
        self.queries = []

    # pylint: disable=too-many-arguments
    def __call__(self, execute, sql, params, many, context):
        current_query = {"sql": sql, "params": params, "many": many}
        start = time.monotonic()
        try:
            result = execute(sql, params, many, context)
        except Exception as err:  # pylint: disable=broad-except
            current_query["status"] = "error"
            current_query["exception"] = err
            raise
        else:
            current_query["status"] = "ok"
            return result
        finally:
            duration = time.monotonic() - start
            current_query["duration"] = duration
            self.queries.append(current_query)


def raise_long_query_runtime(queries, threshold=MAX_QUERY_DURATION):
    """Raises an exception if any query took longer than the threshold"""
    for query in queries:
        if query["duration"] > threshold:
            raise Exception(  # pylint: disable=broad-exception-raised
                "This looks like a slow query:", query["duration"], query["sql"]
            )
