''' url routing for the app and api '''
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path

from bookwyrm import incoming, outgoing, views, settings, wellknown
from bookwyrm import view_actions as actions

username_regex = r'(?P<username>[\w\-_\.]+@[\w\-\_\.]+)'
localname_regex = r'(?P<username>[\w\-_\.]+)'
user_path = r'^user/%s' % username_regex
local_user_path = r'^user/%s' % localname_regex

status_types = [
    'status',
    'review',
    'comment',
    'quotation',
    'boost',
    'generatednote'
]
status_path = r'%s/(%s)/(?P<status_id>\d+)' % \
        (local_user_path, '|'.join(status_types))

book_path = r'^book/(?P<book_id>\d+)'

handler404 = 'bookwyrm.views.not_found_page'
handler500 = 'bookwyrm.views.server_error_page'
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
    re_path(r'^api/v1/instance/peers/?$', wellknown.peers),
    # TODO: re_path(r'^.well-known/host-meta/?$', incoming.host_meta),
    # TODO: robots.txt

    # ui views
    re_path(r'^login/?$', views.login_page),
    re_path(r'^about/?$', views.about_page),
    re_path(r'^password-reset/?$', views.password_reset_request),
    re_path(r'^password-reset/(?P<code>[A-Za-z0-9]+)/?$', views.password_reset),
    re_path(r'^invite/?$', views.manage_invites),
    re_path(r'^invite/(?P<code>[A-Za-z0-9]+)/?$', views.invite_page),

    path('', views.home),
    re_path(r'^(?P<tab>home|local|federated)/?$', views.home_tab),
    re_path(r'^notifications/?$', views.notifications_page),
    re_path(r'^direct-messages/?$', views.direct_messages_page),
    re_path(r'^import/?$', views.import_page),
    re_path(r'^import-status/(\d+)/?$', views.import_status),
    re_path(r'^user-edit/?$', views.edit_profile_page),

    # should return a ui view or activitypub json blob as requested
    # users
    re_path(r'%s/?$' % user_path, views.user_page),
    re_path(r'%s\.json$' % local_user_path, views.user_page),
    re_path(r'%s/?$' % local_user_path, views.user_page),
    re_path(r'%s/shelves/?$' % local_user_path, views.user_shelves_page),
    re_path(r'%s/followers(.json)?/?$' % local_user_path, views.followers_page),
    re_path(r'%s/following(.json)?/?$' % local_user_path, views.following_page),

    # statuses
    re_path(r'%s(.json)?/?$' % status_path, views.status_page),
    re_path(r'%s/activity/?$' % status_path, views.status_page),
    re_path(r'%s/replies(.json)?/?$' % status_path, views.replies_page),

    # books
    re_path(r'%s(.json)?/?$' % book_path, views.book_page),
    re_path(r'%s/edit/?$' % book_path, views.edit_book_page),
    re_path(r'%s/editions(.json)?/?$' % book_path, views.editions_page),

    re_path(r'^author/(?P<author_id>[\w\-]+)(.json)?/?$', views.author_page),
    re_path(r'^tag/(?P<tag_id>.+)\.json/?$', views.tag_page),
    re_path(r'^tag/(?P<tag_id>.+)/?$', views.tag_page),
    re_path(r'^%s/shelf/(?P<shelf_identifier>[\w-]+)(.json)?/?$' % \
            user_path, views.shelf_page),
    re_path(r'^%s/shelf/(?P<shelf_identifier>[\w-]+)(.json)?/?$' % \
            local_user_path, views.shelf_page),

    re_path(r'^search/?$', views.search),

    # internal action endpoints
    re_path(r'^logout/?$', actions.user_logout),
    re_path(r'^user-login/?$', actions.user_login),
    re_path(r'^user-register/?$', actions.register),
    re_path(r'^reset-password-request/?$', actions.password_reset_request),
    re_path(r'^reset-password/?$', actions.password_reset),
    re_path(r'^change-password/?$', actions.password_change),

    re_path(r'^edit-profile/?$', actions.edit_profile),

    re_path(r'^import-data/?$', actions.import_data),
    re_path(r'^retry-import/?$', actions.retry_import),
    re_path(r'^resolve-book/?$', actions.resolve_book),
    re_path(r'^edit-book/(?P<book_id>\d+)/?$', actions.edit_book),
    re_path(r'^upload-cover/(?P<book_id>\d+)/?$', actions.upload_cover),
    re_path(r'^add-description/(?P<book_id>\d+)/?$', actions.add_description),

    re_path(r'^switch-edition/?$', actions.switch_edition),
    re_path(r'^edit-readthrough/?$', actions.edit_readthrough),
    re_path(r'^delete-readthrough/?$', actions.delete_readthrough),

    re_path(r'^rate/?$', actions.rate),
    re_path(r'^review/?$', actions.review),
    re_path(r'^quote/?$', actions.quotate),
    re_path(r'^comment/?$', actions.comment),
    re_path(r'^tag/?$', actions.tag),
    re_path(r'^untag/?$', actions.untag),
    re_path(r'^reply/?$', actions.reply),

    re_path(r'^favorite/(?P<status_id>\d+)/?$', actions.favorite),
    re_path(r'^unfavorite/(?P<status_id>\d+)/?$', actions.unfavorite),
    re_path(r'^boost/(?P<status_id>\d+)/?$', actions.boost),
    re_path(r'^unboost/(?P<status_id>\d+)/?$', actions.unboost),

    re_path(r'^delete-status/(?P<status_id>\d+)/?$', actions.delete_status),

    re_path(r'^create-shelf/?$', actions.create_shelf),
    re_path(r'^edit-shelf/(?P<shelf_id>\d+)?$', actions.edit_shelf),
    re_path(r'^delete-shelf/(?P<shelf_id>\d+)?$', actions.delete_shelf),
    re_path(r'^shelve/?$', actions.shelve),
    re_path(r'^unshelve/?$', actions.unshelve),
    re_path(r'^start-reading/(?P<book_id>\d+)/?$', actions.start_reading),
    re_path(r'^finish-reading/(?P<book_id>\d+)/?$', actions.finish_reading),

    re_path(r'^follow/?$', actions.follow),
    re_path(r'^unfollow/?$', actions.unfollow),
    re_path(r'^accept-follow-request/?$', actions.accept_follow_request),
    re_path(r'^delete-follow-request/?$', actions.delete_follow_request),

    re_path(r'^clear-notifications/?$', actions.clear_notifications),

    re_path(r'^create-invite/?$', actions.create_invite),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
