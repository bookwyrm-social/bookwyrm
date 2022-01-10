""" template filters """
from django import template
from django.db.models import Avg, StdDev, Count, F, Q

from bookwyrm import models
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
def get_book_superlatives():
    """get book stats for the about page"""
    total_ratings = models.Review.objects.filter(local=True, deleted=False).count()
    data = {}
    data["top_rated"] = (
        models.Work.objects.annotate(
            rating=Avg(
                "editions__review__rating",
                filter=Q(editions__review__local=True, editions__review__deleted=False),
            ),
            rating_count=Count(
                "editions__review",
                filter=Q(editions__review__local=True, editions__review__deleted=False),
            ),
        )
        .annotate(weighted=F("rating") * F("rating_count") / total_ratings)
        .filter(rating__gt=4, weighted__gt=0)
        .order_by("-weighted")
        .first()
    )

    data["controversial"] = (
        models.Work.objects.annotate(
            deviation=StdDev(
                "editions__review__rating",
                filter=Q(editions__review__local=True, editions__review__deleted=False),
            ),
            rating_count=Count(
                "editions__review",
                filter=Q(editions__review__local=True, editions__review__deleted=False),
            ),
        )
        .annotate(weighted=F("deviation") * F("rating_count") / total_ratings)
        .filter(weighted__gt=0)
        .order_by("-weighted")
        .first()
    )

    data["wanted"] = (
        models.Work.objects.annotate(
            shelf_count=Count(
                "editions__shelves", filter=Q(editions__shelves__identifier="to-read")
            )
        )
        .order_by("-shelf_count")
        .first()
    )
    return data


@register.simple_tag(takes_context=False)
def related_status(notification):
    """for notifications"""
    if not notification.related_status:
        return None
    return load_subclass(notification.related_status)


@register.simple_tag(takes_context=True)
def active_shelf(context, book):
    """check what shelf a user has a book on, if any"""
    if hasattr(book, "current_shelves"):
        read_shelves = [
            s
            for s in book.current_shelves
            if s.shelf.identifier in models.Shelf.READ_STATUS_IDENTIFIERS
        ]
        return read_shelves[0] if len(read_shelves) else {"book": book}

    shelf = (
        models.ShelfBook.objects.filter(
            shelf__user=context["request"].user,
            book__parent_work__editions=book,
        )
        .select_related("book", "shelf")
        .first()
    )
    return shelf if shelf else {"book": book}


@register.simple_tag(takes_context=False)
def latest_read_through(book, user):
    """the most recent read activity"""
    if hasattr(book, "active_readthroughs"):
        return book.active_readthroughs[0] if len(book.active_readthroughs) else None

    return (
        models.ReadThrough.objects.filter(user=user, book=book, is_active=True)
        .order_by("-start_date")
        .first()
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


@register.simple_tag(takes_context=False)
def get_book_file_links(book):
    """links for a book"""
    return book.file_links.filter(domain__status="approved")
