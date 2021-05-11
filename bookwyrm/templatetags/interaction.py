""" template filters for status interaction buttons """
from django import template
from bookwyrm import models


register = template.Library()


@register.filter(name="liked")
def get_user_liked(user, status):
    """did the given user fav a status?"""
    try:
        models.Favorite.objects.get(user=user, status=status)
        return True
    except models.Favorite.DoesNotExist:
        return False


@register.filter(name="boosted")
def get_user_boosted(user, status):
    """did the given user fav a status?"""
    return user.id in status.boosters.all().values_list("user", flat=True)
