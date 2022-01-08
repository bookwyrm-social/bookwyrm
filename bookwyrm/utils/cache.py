""" Custom handler for caching """
from django.core.cache import cache


def get_or_set(cache_key, function, *args, timeout=None):
    """Django's built-in get_or_set isn't cutting it"""
    value = cache.get(cache_key)
    if value is None:
        cache.set(cache_key, function(*args), timeout=timeout)
    return cache.get(cache_key)
