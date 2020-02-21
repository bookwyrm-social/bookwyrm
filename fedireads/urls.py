''' url routing for the app and api '''
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path

from fedireads import incoming, outgoing, views, settings, wellknown


urlpatterns = [
    path('admin/', admin.site.urls),

    # federation endpoints
    re_path(r'^inbox/?$', incoming.shared_inbox),
    re_path(r'^user/(?P<username>\w+).json/?$', incoming.get_actor),
    re_path(r'^user/(?P<username>\w+)/inbox/?$', incoming.inbox),
    re_path(r'^user/(?P<username>\w+)/outbox/?$', outgoing.outbox),
    re_path(r'^user/(?P<username>\w+)/followers/?$', incoming.get_followers),
    re_path(r'^user/(?P<username>\w+)/following/?$', incoming.get_following),
    re_path(
        r'^user/(?P<username>\w+)/(status|review)/(?P<status_id>\d+)/?$',
        incoming.get_status
    ),
    re_path(
        r'^user/(?P<username>\w+)/(status|review)/(?P<status_id>\d+)/activity/?$',
        incoming.get_status
    ),
    re_path(
        r'^user/(?P<username>\w+)/(status|review)/(?P<status_id>\d+)/replies/?$',
        incoming.get_replies
    ),
    # TODO: shelves need pages in the UI and for their activitypub Collection

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
    re_path(r'^user/(?P<username>[\w@\.-]+)/?$', views.user_profile),
    re_path(r'^user/(?P<username>\w+)/edit/?$', views.user_profile_edit),
    re_path(r'^book/(?P<book_identifier>\w+)/?$', views.book_page),
    re_path(r'^author/(?P<author_identifier>\w+)/?$', views.author_page),
    re_path(r'^tag/(?P<tag_id>[\w-]+)/?$', views.tag_page),

    # internal action endpoints
    re_path(r'^review/?$', views.review),
    re_path(r'^tag/?$', views.tag),
    re_path(r'^untag/?$', views.untag),
    re_path(r'^comment/?$', views.comment),
    re_path(r'^favorite/(?P<status_id>\d+)/?$', views.favorite),
    re_path(
        r'^shelve/(?P<username>\w+)/(?P<shelf_id>[\w-]+)/(?P<book_id>\d+)/?$',
        views.shelve
    ),
    re_path(r'^follow/(?P<username>[\w@\.-]+)/?$', views.follow),
    re_path(r'^unfollow/(?P<username>[\w@\.-]+)/?$', views.unfollow),
    re_path(r'^search/?$', views.search),
    re_path(r'^edit_profile/?$', views.edit_profile),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
