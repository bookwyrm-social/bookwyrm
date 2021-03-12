""" url routing for the app and api """
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path


from bookwyrm import settings, views, wellknown
from bookwyrm.utils import regex

user_path = r"^user/(?P<username>%s)" % regex.username
local_user_path = r"^user/(?P<username>%s)" % regex.localname

status_types = [
    "status",
    "review",
    "reviewrating",
    "comment",
    "quotation",
    "boost",
    "generatednote",
]
status_path = r"%s/(%s)/(?P<status_id>\d+)" % (user_path, "|".join(status_types))

book_path = r"^book/(?P<book_id>\d+)"

handler404 = "bookwyrm.views.not_found_page"
handler500 = "bookwyrm.views.server_error_page"
urlpatterns = [
    path("admin/", admin.site.urls),
    # federation endpoints
    re_path(r"^inbox/?$", views.Inbox.as_view()),
    re_path(r"%s/inbox/?$" % local_user_path, views.Inbox.as_view()),
    re_path(r"%s/outbox/?$" % local_user_path, views.Outbox.as_view()),
    re_path(r"^.well-known/webfinger/?$", wellknown.webfinger),
    re_path(r"^.well-known/nodeinfo/?$", wellknown.nodeinfo_pointer),
    re_path(r"^nodeinfo/2\.0/?$", wellknown.nodeinfo),
    re_path(r"^api/v1/instance/?$", wellknown.instance_info),
    re_path(r"^api/v1/instance/peers/?$", wellknown.peers),
    # polling updates
    re_path("^api/updates/notifications/?$", views.Updates.as_view()),
    # authentication
    re_path(r"^login/?$", views.Login.as_view()),
    re_path(r"^register/?$", views.Register.as_view()),
    re_path(r"^logout/?$", views.Logout.as_view()),
    re_path(r"^password-reset/?$", views.PasswordResetRequest.as_view()),
    re_path(
        r"^password-reset/(?P<code>[A-Za-z0-9]+)/?$", views.PasswordReset.as_view()
    ),
    # admin
    re_path(r"^settings/site-settings", views.Site.as_view(), name="settings-site"),
    re_path(
        r"^settings/federation", views.Federation.as_view(), name="settings-federation"
    ),
    re_path(
        r"^settings/invites/?$", views.ManageInvites.as_view(), name="settings-invites"
    ),
    re_path(r"^invite/(?P<code>[A-Za-z0-9]+)/?$", views.Invite.as_view()),
    # landing pages
    re_path(r"^about/?$", views.About.as_view()),
    path("", views.Home.as_view()),
    re_path(r"^discover/?$", views.Discover.as_view()),
    re_path(r"^notifications/?$", views.Notifications.as_view()),
    # feeds
    re_path(r"^(?P<tab>home|local|federated)/?$", views.Feed.as_view()),
    re_path(r"^direct-messages/?$", views.DirectMessage.as_view()),
    re_path(
        r"^direct-messages/(?P<username>%s)?$" % regex.username,
        views.DirectMessage.as_view(),
    ),
    # search
    re_path(r"^search/?$", views.Search.as_view()),
    # imports
    re_path(r"^import/?$", views.Import.as_view()),
    re_path(r"^import/(\d+)/?$", views.ImportStatus.as_view()),
    # users
    re_path(r"%s/?$" % user_path, views.User.as_view(), name="user-feed"),
    re_path(r"%s\.json$" % user_path, views.User.as_view()),
    re_path(r"%s/rss" % user_path, views.rss_feed.RssFeed(), name="user-rss"),
    re_path(
        r"%s/followers(.json)?/?$" % user_path,
        views.Followers.as_view(),
        name="user-followers",
    ),
    re_path(
        r"%s/following(.json)?/?$" % user_path,
        views.Following.as_view(),
        name="user-following",
    ),
    re_path(r"%s/shelves/?$" % user_path, views.user_shelves_page, name="user-shelves"),
    re_path(r"%s/lists/?$" % user_path, views.UserLists.as_view(), name="user-lists"),
    re_path(
        r"%s/goal/(?P<year>\d{4})/?$" % user_path,
        views.Goal.as_view(),
        name="user-goal",
    ),
    # lists
    re_path(r"^list/?$", views.Lists.as_view(), name="lists"),
    re_path(r"^list/(?P<list_id>\d+)(.json)?/?$", views.List.as_view(), name="list"),
    re_path(
        r"^list/(?P<list_id>\d+)/add/?$", views.list.add_book, name="list-add-book"
    ),
    re_path(
        r"^list/(?P<list_id>\d+)/remove/?$",
        views.list.remove_book,
        name="list-remove-book",
    ),
    re_path(
        r"^list/(?P<list_id>\d+)/curate/?$", views.Curate.as_view(), name="list-curate"
    ),
    # preferences
    re_path(r"^preferences/profile/?$", views.EditUser.as_view(), name="prefs-profile"),
    re_path(r"^preferences/password/?$", views.ChangePassword.as_view()),
    re_path(r"^preferences/block/?$", views.Block.as_view()),
    re_path(r"^block/(?P<user_id>\d+)/?$", views.Block.as_view()),
    re_path(r"^unblock/(?P<user_id>\d+)/?$", views.unblock),
    # statuses
    re_path(r"%s(.json)?/?$" % status_path, views.Status.as_view()),
    re_path(r"%s/activity/?$" % status_path, views.Status.as_view()),
    re_path(r"%s/replies(.json)?/?$" % status_path, views.Replies.as_view()),
    re_path(r"^post/(?P<status_type>\w+)/?$", views.CreateStatus.as_view()),
    re_path(r"^delete-status/(?P<status_id>\d+)/?$", views.DeleteStatus.as_view()),
    # interact
    re_path(r"^favorite/(?P<status_id>\d+)/?$", views.Favorite.as_view()),
    re_path(r"^unfavorite/(?P<status_id>\d+)/?$", views.Unfavorite.as_view()),
    re_path(r"^boost/(?P<status_id>\d+)/?$", views.Boost.as_view()),
    re_path(r"^unboost/(?P<status_id>\d+)/?$", views.Unboost.as_view()),
    # books
    re_path(r"%s(.json)?/?$" % book_path, views.Book.as_view()),
    re_path(r"%s/edit/?$" % book_path, views.EditBook.as_view()),
    re_path(r"%s/confirm/?$" % book_path, views.ConfirmEditBook.as_view()),
    re_path(r"^create-book/?$", views.EditBook.as_view()),
    re_path(r"^create-book/confirm?$", views.ConfirmEditBook.as_view()),
    re_path(r"%s/editions(.json)?/?$" % book_path, views.Editions.as_view()),
    re_path(r"^upload-cover/(?P<book_id>\d+)/?$", views.upload_cover),
    re_path(r"^add-description/(?P<book_id>\d+)/?$", views.add_description),
    re_path(r"^resolve-book/?$", views.resolve_book),
    re_path(r"^switch-edition/?$", views.switch_edition),
    # isbn
    re_path(r"^isbn/(?P<isbn>\d+)(.json)?/?$", views.Isbn.as_view()),
    # author
    re_path(r"^author/(?P<author_id>\d+)(.json)?/?$", views.Author.as_view()),
    re_path(r"^author/(?P<author_id>\d+)/edit/?$", views.EditAuthor.as_view()),
    # tags
    re_path(r"^tag/(?P<tag_id>.+)\.json/?$", views.Tag.as_view()),
    re_path(r"^tag/(?P<tag_id>.+)/?$", views.Tag.as_view()),
    re_path(r"^tag/?$", views.AddTag.as_view()),
    re_path(r"^untag/?$", views.RemoveTag.as_view()),
    # shelf
    re_path(
        r"^%s/shelf/(?P<shelf_identifier>[\w-]+)(.json)?/?$" % user_path,
        views.Shelf.as_view(),
        name="shelf",
    ),
    re_path(
        r"^%s/shelf/(?P<shelf_identifier>[\w-]+)(.json)?/?$" % local_user_path,
        views.Shelf.as_view(),
    ),
    re_path(r"^create-shelf/?$", views.create_shelf, name="shelf-create"),
    re_path(r"^delete-shelf/(?P<shelf_id>\d+)?$", views.delete_shelf),
    re_path(r"^shelve/?$", views.shelve),
    re_path(r"^unshelve/?$", views.unshelve),
    # reading progress
    re_path(r"^edit-readthrough/?$", views.edit_readthrough),
    re_path(r"^delete-readthrough/?$", views.delete_readthrough),
    re_path(r"^create-readthrough/?$", views.create_readthrough),
    re_path(r"^delete-progressupdate/?$", views.delete_progressupdate),
    re_path(r"^start-reading/(?P<book_id>\d+)/?$", views.start_reading),
    re_path(r"^finish-reading/(?P<book_id>\d+)/?$", views.finish_reading),
    # following
    re_path(r"^follow/?$", views.follow),
    re_path(r"^unfollow/?$", views.unfollow),
    re_path(r"^accept-follow-request/?$", views.accept_follow_request),
    re_path(r"^delete-follow-request/?$", views.delete_follow_request),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
