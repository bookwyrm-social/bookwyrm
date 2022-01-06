""" template filters for status interaction buttons """
from django import template
from django.core.cache import cache

from bookwyrm import models


register = template.Library()


@register.filter(name="liked")
def get_user_liked(user, status):
    """did the given user fav a status?"""
    return cache.get_or_set(
        f"fav-{user.id}-{status.id}",
        models.Favorite.objects.filter(user=user, status=status).exists(),
        259200,
    )


@register.filter(name="boosted")
def get_user_boosted(user, status):
    """did the given user fav a status?"""
    return cache.get_or_set(
        f"boost-{user.id}-{status.id}",
        status.boosters.filter(user=user).exists(),
        259200,
    )


@register.filter(name="saved")
def get_user_saved_lists(user, book_list):
    """did the user save a list"""
    return user.saved_lists.filter(id=book_list.id).exists()
