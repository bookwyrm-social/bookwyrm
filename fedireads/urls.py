''' url routing for the app and api '''
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path

from fedireads import incoming, outgoing, views, settings, wellknown
from fedireads import view_actions as actions

username_regex = r'(?P<username>[\w\-_]+@[\w\-\_\.]+)'
localname_regex = r'(?P<username>[\w\-_]+)'
user_path = r'^user/%s' % username_regex
local_user_path = r'^user/%s' % localname_regex
status_path = r'%s/(status|review|comment)/(?P<status_id>\d+)' % local_user_path

urlpatterns = [
    path('admin/', admin.site.urls),

    # federation endpoints
    re_path(r'^inbox/?$', incoming.shared_inbox),
    re_path(r'%s/inbox/?$' % local_user_path, incoming.inbox),
    re_path(r'%s/outbox/?$' % local_user_path, outgoing.outbox),

    # .well-known endpoints
    re_path(r'^.well-known/webfinger/?$', wellknown.webfinger),
    re_path(r'^.well-known/nodeinfo/?$', wellknown.nodeinfo_pointer),
    re_path(r'^nodeinfo/2\.0/?$', wellknown.nodeinfo),
    re_path(r'^api/v1/instance/?$', wellknown.instance_info),
    # TODO: re_path(r'^.well-known/host-meta/?$', incoming.host_meta),

    # ui views
    re_path(r'^login/?$', views.login_page),

    path('', views.home),
    re_path(r'^(?P<tab>home|local|federated)/?$', views.home_tab),
    re_path(r'^notifications/?', views.notifications_page),
    re_path(r'books/?$', views.books_page),
    re_path(r'import/?$', views.import_page),
    re_path(r'user-edit/?$', views.edit_profile_page),

    # should return a ui view or activitypub json blob as requested
    # users
    re_path(r'%s/?$' % user_path, views.user_page),
    re_path(r'%s/?$' % local_user_path, views.user_page),
    re_path(r'%s\.json$' % local_user_path, views.user_page),
    re_path(r'%s/shelves/?$' % local_user_path, views.user_shelves_page),
    re_path(r'%s/followers(.json)?/?$' % local_user_path, views.followers_page),
    re_path(r'%s/following(.json)?/?$' % local_user_path, views.following_page),

    # statuses
    re_path(r'%s(.json)?/?$' % status_path, views.status_page),
    re_path(r'%s/activity/?$' % status_path, views.status_page),
    re_path(r'%s/replies(.json)?/?$' % status_path, views.replies_page),

    # books
    re_path(r'^book/(?P<book_identifier>[\w\-]+)(.json)?/?$', views.book_page),
    re_path(r'^book/(?P<book_identifier>[\w\-]+)/(?P<tab>friends|local|federated)?$', views.book_page),
    re_path(r'^book/(?P<book_identifier>[\w\-]+)/edit/?$', views.edit_book_page),

    re_path(r'^author/(?P<author_identifier>\w+)/?$', views.author_page),
    re_path(r'^tag/(?P<tag_id>.+)/?$', views.tag_page),
    re_path(r'^shelf/%s/(?P<shelf_identifier>[\w-]+)(.json)?/?$' % username_regex, views.shelf_page),
    re_path(r'^shelf/%s/(?P<shelf_identifier>[\w-]+)(.json)?/?$' % localname_regex, views.shelf_page),

    # internal action endpoints
    re_path(r'^logout/?$', actions.user_logout),
    re_path(r'^user-login/?$', actions.user_login),
    re_path(r'^register/?$', actions.register),
    re_path(r'^edit_profile/?$', actions.edit_profile),

    re_path(r'^search/?$', actions.search),
    re_path(r'^import_data/?', actions.import_data),
    re_path(r'^edit_book/(?P<book_id>\d+)/?', actions.edit_book),
    re_path(r'^upload_cover/(?P<book_id>\d+)/?', actions.upload_cover),

    re_path(r'^review/?$', actions.review),
    re_path(r'^comment/?$', actions.comment),
    re_path(r'^tag/?$', actions.tag),
    re_path(r'^untag/?$', actions.untag),
    re_path(r'^reply/?$', actions.reply),

    re_path(r'^favorite/(?P<status_id>\d+)/?$', actions.favorite),
    re_path(r'^unfavorite/(?P<status_id>\d+)/?$', actions.unfavorite),

    re_path(r'^shelve/?$', actions.shelve),

    re_path(r'^follow/?$', actions.follow),
    re_path(r'^unfollow/?$', actions.unfollow),
    re_path(r'^accept_follow_request/?$', actions.accept_follow_request),
    re_path(r'^delete_follow_request/?$', actions.delete_follow_request),

    re_path(r'^clear-notifications/?$', actions.clear_notifications),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
