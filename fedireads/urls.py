''' url routing for the app and api '''
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path

from fedireads import incoming, outgoing, views, settings


urlpatterns = [
    path('admin/', admin.site.urls),

    # federation endpoints
    re_path(r'^inbox/?$', incoming.shared_inbox),
    re_path(r'^user/(?P<username>\w+).json/?$', incoming.get_actor),
    re_path(r'^user/(?P<username>\w+)/inbox/?$', incoming.inbox),
    re_path(r'^user/(?P<username>\w+)/outbox/?$', outgoing.outbox),
    re_path(r'^user/(?P<username>\w+)/followers/?$', incoming.get_followers),
    re_path(r'^user/(?P<username>\w+)/following/?$', incoming.get_following),
    re_path(r'^.well-known/webfinger/?$', incoming.webfinger),
    # TODO: re_path(r'^.well-known/host-meta/?$', incoming.host_meta),

    # ui views
    path(r'', views.home),
    re_path(r'^register/?$', views.register),
    re_path(r'^login/?$', views.user_login),
    re_path(r'^logout/?$', views.user_logout),
    # this endpoint is both ui and fed depending on Accept type
    re_path(r'^user/(?P<username>[\w@\.]+)/?$', views.user_profile),
    re_path(r'^user/(?P<username>\w+)/edit/?$', views.user_profile_edit),
    re_path(r'^work/(?P<book_identifier>\w+)/?$', views.book_page),

    # internal action endpoints
    re_path(r'^review/?$', views.review),
    re_path(r'^shelve/(?P<shelf_id>\w+)/(?P<book_id>\d+)/?$', views.shelve),
    re_path(r'^follow/?$', views.follow),
    re_path(r'^unfollow/?$', views.unfollow),
    re_path(r'^search/?$', views.search),
    re_path(r'^edit_profile/?$', views.edit_profile),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
