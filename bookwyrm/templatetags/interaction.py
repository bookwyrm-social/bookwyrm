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

@register.simple_tag(takes_context=True)
def get_relationship(context, user_object):
    """caches the relationship between the logged in user and another user"""
    user = context["request"].user
    return cache.get(f"relationship-{user.id}-{user_object.id}") or cache.set(
        get_relationship_name(user, user_object),
        timeout=259200,
    )

def get_relationship_name(user, user_object):
    """returns the relationship type"""
    types = {
        "is_following": False,
        "is_follow_pending": False,
        "is_blocked": False,
    }
    if user_object in user.blocks.all():
        types["is_blocked"] = True
    elif user_object in user.following.all():
        types["is_following"] = True
    elif user_object in user.follower_requests.all():
        types["is_follow_pending"] = True
    return types
