''' '''

from django.contrib.syndication.views import Feed
from django.urls import reverse
from bookwyrm.models.user import User
from .helpers import get_activity_feed, get_user_from_username

class RssFeed(Feed):

    description_template = "snippets/rss_content.html"
    title_template = "snippets/rss_title.html"

    def get_object(self, request, username):
        return get_user_from_username(username)

    def link(self, obj):
        return obj.local_path

    def title(self, obj):
        return f"Status updates from {obj.display_name}"


    def items(self, obj):
        return get_activity_feed(obj, ['public', 'unlisted'], queryset=obj.status_set)

    
    def item_link(self, item):
        return item.local_path

