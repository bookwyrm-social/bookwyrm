""" Custom handler for caching """
from django.core.cache import cache


def get_or_set(cache_key, function, *args, timeout=None):
    """Django's built-in get_or_set isn't cutting it"""
    value = cache.get(cache_key)
    if value is None:
        value = function(*args)
        cache.set(cache_key, value, timeout=timeout)
    return value
