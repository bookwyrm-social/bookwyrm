''' serialize user's posts in rss feed '''

from django.contrib.syndication.views import Feed
from .helpers import get_activity_feed, get_user_from_username

# pylint: disable=no-self-use, unused-argument
class RssFeed(Feed):
    ''' serialize user's posts in rss feed '''
    description_template = 'snippets/rss_content.html'
    title_template = 'snippets/rss_title.html'

    def get_object(self, request, username):
        ''' the user who's posts get serialized '''
        return get_user_from_username(request.user, username)


    def link(self, obj):
        ''' link to the user's profile '''
        return obj.local_path


    def title(self, obj):
        ''' title of the rss feed entry '''
        return f'Status updates from {obj.display_name}'


    def items(self, obj):
        ''' the user's activity feed '''
        return get_activity_feed(
            obj,
            privacy=['public', 'unlisted'],
            queryset=obj.status_set.select_subclasses()
        )


    def item_link(self, item):
        ''' link to the status '''
        return item.local_path
