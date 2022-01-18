""" template filters """
from django import template
from django.db.models import Avg

from bookwyrm import models
from bookwyrm.utils import cache


register = template.Library()


@register.filter(name="rating")
def get_rating(book, user):
    """get the overall rating of a book"""
    return cache.get_or_set(
        f"book-rating-{book.parent_work.id}-{user.id}",
        lambda u, b: models.Review.privacy_filter(u)
        .filter(book__parent_work__editions=b, rating__gt=0)
        .aggregate(Avg("rating"))["rating__avg"]
        or 0,
        user,
        book,
        timeout=15552000,
    )


@register.filter(name="user_rating")
def get_user_rating(book, user):
    """get a user's rating of a book"""
    rating = (
        models.Review.objects.filter(
            user=user,
            book=book,
            rating__isnull=False,
            deleted=False,
        )
        .order_by("-published_date")
        .first()
    )
    if rating:
        return rating.rating
    return 0
