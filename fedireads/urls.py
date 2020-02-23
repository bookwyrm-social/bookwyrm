''' url routing for the app and api '''
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path

from fedireads import incoming, outgoing, views, settings, wellknown
from fedireads import view_actions as actions

username_regex = r'(?P<username>[\w@\.-]+)'
localname_regex = r'(?P<username>[\w\.-]+)'
user_path = r'^user/%s' % username_regex
local_user_path = r'^user/%s' % localname_regex
status_path = r'%s/(status|review)/(?P<status_id>\d+)' % local_user_path

urlpatterns = [
    path('admin/', admin.site.urls),

    # federation endpoints
    re_path(r'^inbox/?$', incoming.shared_inbox),
    re_path(r'%s.json/?$' % local_user_path, incoming.get_actor),
    re_path(r'%s/inbox/?$' % local_user_path, incoming.inbox),
    re_path(r'%s/outbox/?$' % local_user_path, outgoing.outbox),
    re_path(r'%s/followers/?$' % local_user_path, incoming.get_followers),
    re_path(r'%s/following/?$' % local_user_path, incoming.get_following),
    re_path(r'%s(/activity/?)?$' % status_path, incoming.get_status),
    re_path(r'%s/replies/?$' % status_path, incoming.get_replies),

    # .well-known endpoints
    re_path(r'^.well-known/webfinger/?$', wellknown.webfinger),
    re_path(r'^.well-known/nodeinfo/?$', wellknown.nodeinfo_pointer),
    re_path(r'^nodeinfo/2\.0/?$', wellknown.nodeinfo),
    re_path(r'^api/v1/instance/?$', wellknown.instance_info),
    # TODO: re_path(r'^.well-known/host-meta/?$', incoming.host_meta),

    # ui views
    path('', views.home),
    re_path(r'^(?P<tab>home|local|federated)/?$', views.home_tab),
    re_path(r'^register/?$', views.register),
    re_path(r'^login/?$', views.user_login),
    re_path(r'^logout/?$', views.user_logout),
    # this endpoint is both ui and fed depending on Accept type
    re_path(r'%s/?$' % user_path, views.user_page),
    re_path(r'%s/edit/?$' % user_path, views.edit_profile_page),
    re_path(r'^user/edit/?$', views.edit_profile_page),
    re_path(r'^book/(?P<book_identifier>\w+)/?$', views.book_page),
    re_path(r'^author/(?P<author_identifier>\w+)/?$', views.author_page),
    re_path(r'^tag/(?P<tag_id>[\w-]+)/?$', views.tag_page),
    re_path(r'^shelf/%s/(?P<shelf_identifier>[\w-]+)/?$' % username_regex, views.shelf_page),

    # internal action endpoints
    re_path(r'^review/?$', actions.review),
    re_path(r'^tag/?$', actions.tag),
    re_path(r'^untag/?$', actions.untag),
    re_path(r'^comment/?$', actions.comment),
    re_path(r'^favorite/(?P<status_id>\d+)/?$', actions.favorite),
    re_path(r'^shelve/?$', actions.shelve),
    re_path(r'^follow/?$', actions.follow),
    re_path(r'^unfollow/?$', actions.unfollow),
    re_path(r'^search/?$', actions.search),
    re_path(r'^edit_profile/?$', actions.edit_profile),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
