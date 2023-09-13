""" Custom handler for caching """
from typing import Any, Callable, Tuple, Union

from django.core.cache import cache


def get_or_set(
    cache_key: str,
    function: Callable[..., Any],
    *args: Tuple[Any, ...],
    timeout: Union[float, None] = None
) -> Any:
    """Django's built-in get_or_set isn't cutting it"""
    value = cache.get(cache_key)
    if value is None:
        value = function(*args)
        cache.set(cache_key, value, timeout=timeout)
    return value
