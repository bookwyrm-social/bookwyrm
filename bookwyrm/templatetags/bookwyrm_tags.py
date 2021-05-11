""" template filters """
from django import template
from django.db.models import Avg

from bookwyrm import models, views
from bookwyrm.views.status import to_markdown
from bookwyrm.templatetags.utilities import get_user_identifier


register = template.Library()


@register.filter(name="rating")
def get_rating(book, user):
    """get the overall rating of a book"""
    queryset = views.helpers.privacy_filter(
        user, models.Review.objects.filter(book=book)
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
        )
        .order_by("-published_date")
        .first()
    )
    if rating:
        return rating.rating
    return 0


@register.filter(name="replies")
def get_replies(status):
    """get all direct replies to a status"""
    # TODO: this limit could cause problems
    return models.Status.objects.filter(
        reply_parent=status,
        deleted=False,
    ).select_subclasses()[:10]


@register.filter(name="parent")
def get_parent(status):
    """get the reply parent for a status"""
    return (
        models.Status.objects.filter(id=status.reply_parent_id)
        .select_subclasses()
        .get()
    )


@register.filter(name="boosted_status")
def get_boosted(boost):
    """load a boosted status. have to do this or it won't get foreign keys"""
    return (
        models.Status.objects.select_subclasses().get(id=boost.boosted_status.id)
    )


@register.filter(name="book_description")
def get_book_description(book):
    """use the work's text if the book doesn't have it"""
    return book.description or book.parent_work.description


@register.filter(name="to_markdown")
def get_markdown(content):
    """convert markdown to html"""
    if content:
        return to_markdown(content)
    return None


@register.filter(name="mentions")
def get_mentions(status, user):
    """people to @ in a reply: the parent and all mentions"""
    mentions = set([status.user] + list(status.mention_users.all()))
    return (
        " ".join("@" + get_user_identifier(m) for m in mentions if not m == user) + " "
    )


@register.filter(name="next_shelf")
def get_next_shelf(current_shelf):
    """shelf you'd use to update reading progress"""
    if current_shelf == "to-read":
        return "reading"
    if current_shelf == "reading":
        return "read"
    if current_shelf == "read":
        return "read"
    return "to-read"


@register.simple_tag(takes_context=False)
def related_status(notification):
    """for notifications"""
    if not notification.related_status:
        return None
    if hasattr(notification.related_status, "quotation"):
        return notification.related_status.quotation
    if hasattr(notification.related_status, "review"):
        return notification.related_status.review
    if hasattr(notification.related_status, "comment"):
        return notification.related_status.comment
    return notification.related_status


@register.simple_tag(takes_context=True)
def active_shelf(context, book):
    """check what shelf a user has a book on, if any"""
    shelf = models.ShelfBook.objects.filter(
        shelf__user=context["request"].user, book__in=book.parent_work.editions.all()
    ).first()
    return shelf if shelf else {"book": book}


@register.simple_tag(takes_context=False)
def latest_read_through(book, user):
    """the most recent read activity"""
    return (
        models.ReadThrough.objects.filter(user=user, book=book)
        .order_by("-start_date")
        .first()
    )


@register.simple_tag(takes_context=True)
def mutuals_count(context, user):
    """how many users that you follow, follow them"""
    viewer = context["request"].user
    if not viewer.is_authenticated:
        return None
    return user.followers.filter(id__in=viewer.following.all()).count()
