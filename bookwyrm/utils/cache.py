""" Custom handler for caching """
from typing import Callable, Optional, ParamSpec, TypeVar, cast

from django.core.cache import cache

Args = ParamSpec("Args")
Ret = TypeVar("Ret")


def get_or_set(
    cache_key: str,
    function: Callable[Args, Ret],
    *args: Args.args,
    timeout: Optional[float] = None
) -> Ret:
    """Django's built-in get_or_set isn't cutting it"""
    value = cast(Optional[Ret], cache.get(cache_key))
    if value is None:
        value = function(*args)
        cache.set(cache_key, value, timeout=timeout)
    return value
