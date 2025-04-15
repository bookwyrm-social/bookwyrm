""" serialize user's posts in rss feed """

from django.contrib.syndication.views import Feed
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _
from django.shortcuts import get_object_or_404
from ..models import Review, Quotation, Comment

from .helpers import get_user_from_username

# pylint: disable=no-self-use
class RssFeed(Feed):
    """serialize user's posts in rss feed"""

    description_template = "rss/content.html"

    def item_title(self, item):
        """render the item title"""
        if hasattr(item, "pure_name") and item.pure_name:
            return item.pure_name
        title_template = get_template("snippets/status/header_content.html")
        title = title_template.render({"status": item})
        template = get_template("rss/title.html")
        return template.render({"user": item.user, "item_title": title}).strip()

    def get_object(self, request, username):  # pylint: disable=arguments-differ
        """the user who's posts get serialized"""
        return get_user_from_username(request.user, username)

    def link(self, obj):
        """link to the user's profile"""
        return obj.local_path

    def title(self, obj):
        """title of the rss feed entry"""
        return _(f"Status updates from {obj.display_name}")

    def items(self, obj):
        """the user's activity feed"""
        return (
            obj.status_set.select_subclasses()
            .filter(
                privacy__in=["public", "unlisted"],
            )
            .order_by("-published_date")[:10]
        )

    def item_link(self, item):
        """link to the status"""
        return item.local_path

    def item_pubdate(self, item):
        """publication date of the item"""
        return item.published_date


class RssReviewsOnlyFeed(Feed):
    """serialize user's reviews in rss feed"""

    description_template = "rss/content.html"

    def item_title(self, item):
        """render the item title"""
        if hasattr(item, "pure_name") and item.pure_name:
            return item.pure_name
        title_template = get_template("snippets/status/header_content.html")
        title = title_template.render({"status": item})
        template = get_template("rss/title.html")
        return template.render({"user": item.user, "item_title": title}).strip()

    def get_object(self, request, username):  # pylint: disable=arguments-differ
        """the user who's posts get serialized"""
        return get_user_from_username(request.user, username)

    def link(self, obj):
        """link to the user's profile"""
        return obj.local_path

    def title(self, obj):
        """title of the rss feed entry"""
        return _(f"Reviews from {obj.display_name}")

    def items(self, obj):
        """the user's activity feed"""
        return Review.objects.filter(
            user=obj,
            privacy__in=["public", "unlisted"],
        ).order_by("-published_date")[:10]

    def item_link(self, item):
        """link to the status"""
        return item.local_path

    def item_pubdate(self, item):
        """publication date of the item"""
        return item.published_date


class RssQuotesOnlyFeed(Feed):
    """serialize user's quotes in rss feed"""

    description_template = "rss/content.html"

    def item_title(self, item):
        """render the item title"""
        if hasattr(item, "pure_name") and item.pure_name:
            return item.pure_name
        title_template = get_template("snippets/status/header_content.html")
        title = title_template.render({"status": item})
        template = get_template("rss/title.html")
        return template.render({"user": item.user, "item_title": title}).strip()

    def get_object(self, request, username):  # pylint: disable=arguments-differ
        """the user who's posts get serialized"""
        return get_user_from_username(request.user, username)

    def link(self, obj):
        """link to the user's profile"""
        return obj.local_path

    def title(self, obj):
        """title of the rss feed entry"""
        return _(f"Quotes from {obj.display_name}")

    def items(self, obj):
        """the user's activity feed"""
        return Quotation.objects.filter(
            user=obj,
            privacy__in=["public", "unlisted"],
        ).order_by("-published_date")[:10]

    def item_link(self, item):
        """link to the status"""
        return item.local_path

    def item_pubdate(self, item):
        """publication date of the item"""
        return item.published_date


class RssCommentsOnlyFeed(Feed):
    """serialize user's quotes in rss feed"""

    description_template = "rss/content.html"

    def item_title(self, item):
        """render the item title"""
        if hasattr(item, "pure_name") and item.pure_name:
            return item.pure_name
        title_template = get_template("snippets/status/header_content.html")
        title = title_template.render({"status": item})
        template = get_template("rss/title.html")
        return template.render({"user": item.user, "item_title": title}).strip()

    def get_object(self, request, username):  # pylint: disable=arguments-differ
        """the user who's posts get serialized"""
        return get_user_from_username(request.user, username)

    def link(self, obj):
        """link to the user's profile"""
        return obj.local_path

    def title(self, obj):
        """title of the rss feed entry"""
        return _(f"Comments from {obj.display_name}")

    def items(self, obj):
        """the user's activity feed"""
        return Comment.objects.filter(
            user=obj,
            privacy__in=["public", "unlisted"],
        ).order_by("-published_date")[:10]

    def item_link(self, item):
        """link to the status"""
        return item.local_path

    def item_pubdate(self, item):
        """publication date of the item"""
        return item.published_date


class RssShelfFeed(Feed):
    """serialize a shelf activity in rss"""

    description_template = "rss/edition.html"

    def item_title(self, item):
        """render the item title"""
        authors = item.authors
        if item.author_text:
            authors.display_name = f"{item.author_text}:"
        else:
            authors.description = ""
        template = get_template("rss/title.html")
        return template.render({"user": authors, "item_title": item.title}).strip()

    def get_object(
        self, request, shelf_identifier, username
    ):  # pylint: disable=arguments-differ
        """the shelf that gets serialized"""
        user = get_user_from_username(request.user, username)
        # always get privacy, don't support rss over anything private
        # get the SHELF of the object
        shelf = get_object_or_404(
            user.shelf_set,
            identifier=shelf_identifier,
            privacy__in=["public", "unlisted"],
        )
        shelf.raise_visible_to_user(request.user)
        return shelf

    def link(self, obj):
        """link to the shelf"""
        return obj.local_path

    def title(self, obj):
        """title of the rss feed entry"""
        return _(f"{obj.user.display_name}’s {obj.name} shelf")

    def items(self, obj):
        """the user's activity feed"""
        return obj.books.order_by("-shelfbook__shelved_date")[:10]

    def item_link(self, item):
        """link to the status"""
        return item.local_path

    def item_pubdate(self, item):
        """publication date of the item"""
        return item.published_date

    def description(self, obj):
        """description of the shelf including the shelf name and user."""
        # if there's a description, lets add it. Not everyone puts a description in.
        if desc := obj.description:
            return _(f"{obj.user.display_name}’s {obj.name} shelf: {desc}")
        return _(f"Books added to {obj.user.name}’s {obj.name} shelf")
