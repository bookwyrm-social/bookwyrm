""" serialize user's posts in rss feed """

from django.contrib.syndication.views import Feed
from .helpers import get_user_from_username, privacy_filter

# pylint: disable=no-self-use, unused-argument
class RssFeed(Feed):
    """serialize user's posts in rss feed"""

    description_template = "rss/content.html"
    title_template = "rss/title.html"

    def get_object(self, request, username):
        """the user who's posts get serialized"""
        return get_user_from_username(request.user, username)

    def link(self, obj):
        """link to the user's profile"""
        return obj.local_path

    def title(self, obj):
        """title of the rss feed entry"""
        return f"Status updates from {obj.display_name}"

    def items(self, obj):
        """the user's activity feed"""
        return privacy_filter(
            obj,
            obj.status_set.select_subclasses(),
            privacy_levels=["public", "unlisted"],
        )

    def item_link(self, item):
        """link to the status"""
        return item.local_path
