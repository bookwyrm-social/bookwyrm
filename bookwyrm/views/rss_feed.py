""" serialize user's posts in rss feed """

from django.contrib.syndication.views import Feed
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _

from bookwyrm import models
from .helpers import get_user_from_username

# pylint: disable=no-self-use, unused-argument
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
        return models.Status.privacy_filter(
            obj,
            privacy_levels=["public", "unlisted"],
        ).filter(user=obj)

    def item_link(self, item):
        """link to the status"""
        return item.local_path
