""" url routing for the app and api """
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path
from django.views.generic.base import TemplateView

from bookwyrm import settings, views
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

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
    # federation endpoints
    re_path(r"^inbox/?$", views.Inbox.as_view()),
    re_path(r"%s/inbox/?$" % local_user_path, views.Inbox.as_view()),
    re_path(r"%s/outbox/?$" % local_user_path, views.Outbox.as_view()),
    re_path(r"^\.well-known/webfinger/?$", views.webfinger),
    re_path(r"^\.well-known/nodeinfo/?$", views.nodeinfo_pointer),
    re_path(r"^\.well-known/host-meta/?$", views.host_meta),
    re_path(r"^nodeinfo/2\.0/?$", views.nodeinfo),
    re_path(r"^api/v1/instance/?$", views.instance_info),
    re_path(r"^api/v1/instance/peers/?$", views.peers),
    # polling updates
    re_path("^api/updates/notifications/?$", views.get_notification_count),
    re_path("^api/updates/stream/(?P<stream>[a-z]+)/?$", views.get_unread_status_count),
    # authentication
    re_path(r"^login/?$", views.Login.as_view(), name="login"),
    re_path(r"^register/?$", views.Register.as_view()),
    re_path(r"^logout/?$", views.Logout.as_view(), name="logout"),
    re_path(
        r"^password-reset/?$",
        views.PasswordResetRequest.as_view(),
        name="password-reset",
    ),
    re_path(
        r"^password-reset/(?P<code>[A-Za-z0-9]+)/?$", views.PasswordReset.as_view()
    ),
    # admin
    re_path(r"^settings/site-settings/?$", views.Site.as_view(), name="settings-site"),
    re_path(
        r"^settings/announcements/?$",
        views.Announcements.as_view(),
        name="settings-announcements",
    ),
    re_path(
        r"^settings/announcements/(?P<announcement_id>\d+)/?$",
        views.Announcement.as_view(),
        name="settings-announcements",
    ),
    re_path(
        r"^settings/announcements/(?P<announcement_id>\d+)/delete/?$",
        views.delete_announcement,
        name="settings-announcements-delete",
    ),
    re_path(
        r"^settings/email-preview/?$",
        views.site.email_preview,
        name="settings-email-preview",
    ),
    re_path(
        r"^settings/users/?$", views.UserAdminList.as_view(), name="settings-users"
    ),
    re_path(
        r"^settings/users/(?P<user>\d+)/?$",
        views.UserAdmin.as_view(),
        name="settings-user",
    ),
    re_path(
        r"^settings/federation/?$",
        views.Federation.as_view(),
        name="settings-federation",
    ),
    re_path(
        r"^settings/federation/(?P<server>\d+)/?$",
        views.FederatedServer.as_view(),
        name="settings-federated-server",
    ),
    re_path(
        r"^settings/federation/(?P<server>\d+)/block?$",
        views.federation.block_server,
        name="settings-federated-server-block",
    ),
    re_path(
        r"^settings/federation/(?P<server>\d+)/unblock?$",
        views.federation.unblock_server,
        name="settings-federated-server-unblock",
    ),
    re_path(
        r"^settings/federation/add/?$",
        views.AddFederatedServer.as_view(),
        name="settings-add-federated-server",
    ),
    re_path(
        r"^settings/federation/import/?$",
        views.ImportServerBlocklist.as_view(),
        name="settings-import-blocklist",
    ),
    re_path(
        r"^settings/invites/?$", views.ManageInvites.as_view(), name="settings-invites"
    ),
    re_path(
        r"^settings/requests/?$",
        views.ManageInviteRequests.as_view(),
        name="settings-invite-requests",
    ),
    re_path(
        r"^settings/requests/ignore?$",
        views.ignore_invite_request,
        name="settings-invite-requests-ignore",
    ),
    re_path(
        r"^invite-request/?$", views.InviteRequest.as_view(), name="invite-request"
    ),
    re_path(r"^invite/(?P<code>[A-Za-z0-9]+)/?$", views.Invite.as_view()),
    # moderation
    re_path(r"^settings/reports/?$", views.Reports.as_view(), name="settings-reports"),
    re_path(
        r"^settings/reports/(?P<report_id>\d+)/?$",
        views.Report.as_view(),
        name="settings-report",
    ),
    re_path(
        r"^settings/reports/(?P<user_id>\d+)/suspend/?$",
        views.suspend_user,
        name="settings-report-suspend",
    ),
    re_path(
        r"^settings/reports/(?P<report_id>\d+)/resolve/?$",
        views.resolve_report,
        name="settings-report-resolve",
    ),
    re_path(r"^report/?$", views.make_report, name="report"),
    # landing pages
    re_path(r"^about/?$", views.About.as_view(), name="about"),
    path("", views.Home.as_view(), name="landing"),
    re_path(r"^discover/?$", views.Discover.as_view()),
    re_path(r"^notifications/?$", views.Notifications.as_view(), name="notifications"),
    re_path(
        r"^notifications/(?P<notification_type>mentions)/?$",
        views.Notifications.as_view(),
        name="notifications",
    ),
    re_path(r"^directory/?", views.Directory.as_view(), name="directory"),
    # Get started
    re_path(
        r"^get-started/profile/?$",
        views.GetStartedProfile.as_view(),
        name="get-started-profile",
    ),
    re_path(
        r"^get-started/books/?$",
        views.GetStartedBooks.as_view(),
        name="get-started-books",
    ),
    re_path(
        r"^get-started/users/?$",
        views.GetStartedUsers.as_view(),
        name="get-started-users",
    ),
    # feeds
    re_path(r"^(?P<tab>home|local|federated)/?$", views.Feed.as_view()),
    re_path(
        r"^direct-messages/?$", views.DirectMessage.as_view(), name="direct-messages"
    ),
    re_path(
        r"^direct-messages/(?P<username>%s)?$" % regex.username,
        views.DirectMessage.as_view(),
        name="direct-messages-user",
    ),
    # search
    re_path(r"^search/?$", views.Search.as_view(), name="search"),
    # imports
    re_path(r"^import/?$", views.Import.as_view(), name="import"),
    re_path(r"^import/(\d+)/?$", views.ImportStatus.as_view(), name="import-status"),
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
    # lists
    re_path(r"%s/lists/?$" % user_path, views.UserLists.as_view(), name="user-lists"),
    re_path(r"^list/?$", views.Lists.as_view(), name="lists"),
    re_path(r"^list/(?P<list_id>\d+)(.json)?/?$", views.List.as_view(), name="list"),
    re_path(r"^list/add-book/?$", views.list.add_book, name="list-add-book"),
    re_path(
        r"^list/(?P<list_id>\d+)/remove/?$",
        views.list.remove_book,
        name="list-remove-book",
    ),
    re_path(
        r"^list-item/(?P<list_item_id>\d+)/set-position$",
        views.list.set_book_position,
        name="list-set-book-position",
    ),
    re_path(
        r"^list/(?P<list_id>\d+)/curate/?$", views.Curate.as_view(), name="list-curate"
    ),
    # User books
    re_path(r"%s/books/?$" % user_path, views.Shelf.as_view(), name="user-shelves"),
    re_path(
        r"^%s/(helf|books)/(?P<shelf_identifier>[\w-]+)(.json)?/?$" % user_path,
        views.Shelf.as_view(),
        name="shelf",
    ),
    re_path(
        r"^%s/(books|shelf)/(?P<shelf_identifier>[\w-]+)(.json)?/?$" % local_user_path,
        views.Shelf.as_view(),
        name="shelf",
    ),
    re_path(r"^create-shelf/?$", views.create_shelf, name="shelf-create"),
    re_path(r"^delete-shelf/(?P<shelf_id>\d+)?$", views.delete_shelf),
    re_path(r"^shelve/?$", views.shelve),
    re_path(r"^unshelve/?$", views.unshelve),
    # goals
    re_path(
        r"%s/goal/(?P<year>\d{4})/?$" % user_path,
        views.Goal.as_view(),
        name="user-goal",
    ),
    re_path(r"^hide-goal/?$", views.hide_goal, name="hide-goal"),
    # preferences
    re_path(r"^preferences/profile/?$", views.EditUser.as_view(), name="prefs-profile"),
    re_path(
        r"^preferences/password/?$",
        views.ChangePassword.as_view(),
        name="prefs-password",
    ),
    re_path(r"^preferences/delete/?$", views.DeleteUser.as_view(), name="prefs-delete"),
    re_path(r"^preferences/block/?$", views.Block.as_view(), name="prefs-block"),
    re_path(r"^block/(?P<user_id>\d+)/?$", views.Block.as_view()),
    re_path(r"^unblock/(?P<user_id>\d+)/?$", views.unblock),
    # statuses
    re_path(r"%s(.json)?/?$" % status_path, views.Status.as_view(), name="status"),
    re_path(r"%s/activity/?$" % status_path, views.Status.as_view(), name="status"),
    re_path(
        r"%s/replies(.json)?/?$" % status_path, views.Replies.as_view(), name="replies"
    ),
    re_path(
        r"^post/?$",
        views.CreateStatus.as_view(),
        name="create-status",
    ),
    re_path(
        r"^post/(?P<status_type>\w+)/?$",
        views.CreateStatus.as_view(),
        name="create-status",
    ),
    re_path(
        r"^delete-status/(?P<status_id>\d+)/?$",
        views.DeleteStatus.as_view(),
        name="delete-status",
    ),
    re_path(
        r"^redraft-status/(?P<status_id>\d+)/?$",
        views.DeleteAndRedraft.as_view(),
        name="redraft",
    ),
    # interact
    re_path(r"^favorite/(?P<status_id>\d+)/?$", views.Favorite.as_view()),
    re_path(r"^unfavorite/(?P<status_id>\d+)/?$", views.Unfavorite.as_view()),
    re_path(r"^boost/(?P<status_id>\d+)/?$", views.Boost.as_view()),
    re_path(r"^unboost/(?P<status_id>\d+)/?$", views.Unboost.as_view()),
    # books
    re_path(r"%s(.json)?/?$" % book_path, views.Book.as_view(), name="book"),
    re_path(
        r"%s/(?P<user_statuses>review|comment|quote)/?$" % book_path,
        views.Book.as_view(),
        name="book-user-statuses",
    ),
    re_path(r"%s/edit/?$" % book_path, views.EditBook.as_view()),
    re_path(r"%s/confirm/?$" % book_path, views.ConfirmEditBook.as_view()),
    re_path(r"^create-book/?$", views.EditBook.as_view(), name="create-book"),
    re_path(r"^create-book/confirm?$", views.ConfirmEditBook.as_view()),
    re_path(r"%s/editions(.json)?/?$" % book_path, views.Editions.as_view()),
    re_path(
        r"^upload-cover/(?P<book_id>\d+)/?$", views.upload_cover, name="upload-cover"
    ),
    re_path(r"^add-description/(?P<book_id>\d+)/?$", views.add_description),
    re_path(r"^resolve-book/?$", views.resolve_book),
    re_path(r"^switch-edition/?$", views.switch_edition),
    # isbn
    re_path(r"^isbn/(?P<isbn>\d+)(.json)?/?$", views.Isbn.as_view()),
    # author
    re_path(r"^author/(?P<author_id>\d+)(.json)?/?$", views.Author.as_view()),
    re_path(r"^author/(?P<author_id>\d+)/edit/?$", views.EditAuthor.as_view()),
    # reading progress
    re_path(r"^edit-readthrough/?$", views.edit_readthrough, name="edit-readthrough"),
    re_path(r"^delete-readthrough/?$", views.delete_readthrough),
    re_path(r"^create-readthrough/?$", views.create_readthrough),
    re_path(r"^delete-progressupdate/?$", views.delete_progressupdate),
    # shelve actions
    re_path(
        r"^reading-status/(?P<status>want|start|finish)/(?P<book_id>\d+)/?$",
        views.ReadingStatus.as_view(),
        name="reading-status",
    ),
    # following
    re_path(r"^follow/?$", views.follow, name="follow"),
    re_path(r"^unfollow/?$", views.unfollow, name="unfollow"),
    re_path(r"^accept-follow-request/?$", views.accept_follow_request),
    re_path(r"^delete-follow-request/?$", views.delete_follow_request),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
