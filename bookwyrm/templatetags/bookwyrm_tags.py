""" template filters """
from django import template
from django.db.models import Avg

from bookwyrm import models
from bookwyrm.utils import cache
from bookwyrm.views.feed import get_suggested_books


register = template.Library()


@register.filter(name="rating")
def get_rating(book, user):
    """get the overall rating of a book"""
    queryset = models.Review.privacy_filter(user).filter(
        book__parent_work__editions=book
    )
    return queryset.aggregate(Avg("rating"))["rating__avg"]


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


@register.filter(name="book_description")
def get_book_description(book):
    """use the work's text if the book doesn't have it"""
    return book.description or book.parent_work.description


@register.filter(name="next_shelf")
def get_next_shelf(current_shelf):
    """shelf you'd use to update reading progress"""
    if current_shelf == "to-read":
        return "reading"
    if current_shelf == "reading":
        return "read"
    if current_shelf == "read":
        return "complete"
    return "to-read"


@register.filter(name="load_subclass")
def load_subclass(status):
    """sometimes you didn't select_subclass"""
    if hasattr(status, "quotation"):
        return status.quotation
    if hasattr(status, "review"):
        return status.review
    if hasattr(status, "comment"):
        return status.comment
    if hasattr(status, "generatednote"):
        return status.generatednote
    return status


@register.simple_tag(takes_context=False)
def related_status(notification):
    """for notifications"""
    if not notification.related_status:
        return None
    return load_subclass(notification.related_status)


@register.simple_tag(takes_context=True)
def active_shelf(context, book):
    """check what shelf a user has a book on, if any"""
    user = context["request"].user
    return cache.get_or_set(
        f"active_shelf-{user.id}-{book.id}",
        lambda u, b: (
            models.ShelfBook.objects.filter(
                shelf__user=u,
                book__parent_work__editions=b,
            ).first()
        )
        or {"book": book},
        user,
        book,
        timeout=15552000,
    )


@register.simple_tag(takes_context=False)
def latest_read_through(book, user):
    """the most recent read activity"""
    return cache.get_or_set(
        f"latest_read_through-{user.id}-{book.id}",
        lambda u, b: (
            models.ReadThrough.objects.filter(user=u, book=b, is_active=True)
            .order_by("-start_date")
            .first()
        ),
        user,
        book,
        timeout=15552000,
    )


@register.simple_tag(takes_context=False)
def get_landing_books():
    """list of books for the landing page"""
    return list(
        set(
            models.Edition.objects.filter(
                review__published_date__isnull=False,
                review__deleted=False,
                review__user__local=True,
                review__privacy__in=["public", "unlisted"],
            )
            .exclude(cover__exact="")
            .distinct()
            .order_by("-review__published_date")[:6]
        )
    )


@register.simple_tag(takes_context=True)
def mutuals_count(context, user):
    """how many users that you follow, follow them"""
    viewer = context["request"].user
    if not viewer.is_authenticated:
        return None
    return user.followers.filter(followers=viewer).count()


@register.simple_tag(takes_context=True)
def suggested_books(context):
    """get books for suggested books panel"""
    # this happens here instead of in the view so that the template snippet can
    # be cached in the template
    return get_suggested_books(context["request"].user)
