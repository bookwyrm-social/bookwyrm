""" url routing for the app and api """
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, re_path
from django.views.generic.base import TemplateView

from bookwyrm import settings, views
from bookwyrm.utils import regex

USER_PATH = rf"^user/(?P<username>{regex.USERNAME})"
LOCAL_USER_PATH = rf"^user/(?P<username>{regex.LOCALNAME})"

status_types = [
    "status",
    "review",
    "reviewrating",
    "comment",
    "quotation",
    "boost",
    "generatednote",
]

STATUS_TYPES_STRING = "|".join(status_types)
STATUS_PATH = rf"{USER_PATH}/({STATUS_TYPES_STRING})/(?P<status_id>\d+)"

BOOK_PATH = r"^book/(?P<book_id>\d+)"

STREAMS = "|".join(s["key"] for s in settings.STREAMS)

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
    path(
        "manifest.json",
        TemplateView.as_view(
            template_name="manifest.json", content_type="application/json"
        ),
    ),
    # federation endpoints
    re_path(r"^inbox/?$", views.Inbox.as_view(), name="inbox"),
    re_path(rf"{LOCAL_USER_PATH}/inbox/?$", views.Inbox.as_view(), name="user_inbox"),
    re_path(
        rf"{LOCAL_USER_PATH}/outbox/?$", views.Outbox.as_view(), name="user_outbox"
    ),
    re_path(r"^\.well-known/webfinger/?$", views.webfinger),
    re_path(r"^\.well-known/nodeinfo/?$", views.nodeinfo_pointer),
    re_path(r"^\.well-known/host-meta/?$", views.host_meta),
    re_path(r"^nodeinfo/2\.0/?$", views.nodeinfo),
    re_path(r"^api/v1/instance/?$", views.instance_info),
    re_path(r"^api/v1/instance/peers/?$", views.peers),
    re_path(r"^opensearch.xml$", views.opensearch, name="opensearch"),
    re_path(r"^ostatus_subscribe/?$", views.ostatus_follow_request),
    # polling updates
    re_path(
        "^api/updates/notifications/?$",
        views.get_notification_count,
        name="notification-updates",
    ),
    re_path(
        "^api/updates/stream/(?P<stream>[a-z]+)/?$",
        views.get_unread_status_string,
        name="stream-updates",
    ),
    # instance setup
    re_path(r"^setup/?$", views.InstanceConfig.as_view(), name="setup"),
    re_path(r"^setup/admin/?$", views.CreateAdmin.as_view(), name="setup-admin"),
    # authentication
    re_path(r"^login/?$", views.Login.as_view(), name="login"),
    re_path(r"^login/(?P<confirmed>confirmed)/?$", views.Login.as_view(), name="login"),
    re_path(r"^register/?$", views.Register.as_view()),
    re_path(r"confirm-email/?$", views.ConfirmEmail.as_view(), name="confirm-email"),
    re_path(
        r"confirm-email/(?P<code>[A-Za-z0-9]+)/?$",
        views.ConfirmEmailCode.as_view(),
        name="confirm-email-code",
    ),
    re_path(r"^resend-link/?$", views.ResendConfirmEmail.as_view(), name="resend-link"),
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
    re_path(
        r"^settings/dashboard/?$", views.Dashboard.as_view(), name="settings-dashboard"
    ),
    re_path(r"^settings/site-settings/?$", views.Site.as_view(), name="settings-site"),
    re_path(
        r"^settings/site-registration/?$",
        views.RegistrationLimited.as_view(),
        name="settings-registration-limited",
    ),
    re_path(
        r"^settings/site-registration-admin/?$",
        views.Registration.as_view(),
        name="settings-registration",
    ),
    re_path(r"^settings/themes/?$", views.Themes.as_view(), name="settings-themes"),
    re_path(
        r"^settings/themes/(?P<theme_id>\d+)/delete/?$",
        views.delete_theme,
        name="settings-themes-delete",
    ),
    re_path(
        r"^settings/themes/(?P<theme_id>\d+)/test/?$",
        views.test_theme,
        name="settings-themes-test",
    ),
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
        r"^settings/announcements/create/?$",
        views.EditAnnouncement.as_view(),
        name="settings-announcements-edit",
    ),
    re_path(
        r"^settings/announcements/(?P<announcement_id>\d+)/edit/?$",
        views.EditAnnouncement.as_view(),
        name="settings-announcements-edit",
    ),
    re_path(
        r"^settings/announcements/(?P<announcement_id>\d+)/delete/?$",
        views.delete_announcement,
        name="settings-announcements-delete",
    ),
    re_path(
        r"^settings/email-preview/?$",
        views.admin.email_config.email_preview,
        name="settings-email-preview",
    ),
    re_path(
        r"^settings/users/?$", views.UserAdminList.as_view(), name="settings-users"
    ),
    re_path(
        r"^settings/users/(?P<status>(local|federated|deleted))\/?$",
        views.UserAdminList.as_view(),
        name="settings-users",
    ),
    re_path(
        r"^settings/users/(?P<user_id>\d+)/(?P<report_id>\d+)?$",
        views.UserAdmin.as_view(),
        name="settings-user",
    ),
    re_path(
        r"^settings/users/(?P<user_id>\d+)/activate/?$",
        views.ActivateUserAdmin.as_view(),
        name="settings-activate-user",
    ),
    re_path(
        r"^settings/federation/(?P<status>(federated|blocked))?/?$",
        views.Federation.as_view(),
        name="settings-federation",
    ),
    re_path(
        r"^settings/federation/(?P<server>\d+)/?$",
        views.FederatedServer.as_view(),
        name="settings-federated-server",
    ),
    re_path(
        r"^settings/federation/(?P<server>\d+)/block/?$",
        views.block_server,
        name="settings-federated-server-block",
    ),
    re_path(
        r"^settings/federation/(?P<server>\d+)/unblock/?$",
        views.unblock_server,
        name="settings-federated-server-unblock",
    ),
    re_path(
        r"^settings/federation/(?P<server>\d+)/refresh/?$",
        views.refresh_server,
        name="settings-federated-server-refresh",
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
        r"^settings/requests/ignore/?$",
        views.ignore_invite_request,
        name="settings-invite-requests-ignore",
    ),
    re_path(
        r"^invite-request/?$", views.InviteRequest.as_view(), name="invite-request"
    ),
    re_path(
        r"^invite/(?P<code>[A-Za-z0-9]+)/?$", views.Invite.as_view(), name="invite"
    ),
    re_path(
        r"^settings/email-blocklist/?$",
        views.EmailBlocklist.as_view(),
        name="settings-email-blocks",
    ),
    re_path(
        r"^settings/email-blocks/(?P<domain_id>\d+)/delete/?$",
        views.EmailBlocklist.as_view(),
        name="settings-email-blocks-delete",
    ),
    re_path(
        r"^setting/link-domains/?$",
        views.LinkDomain.as_view(),
        name="settings-link-domain",
    ),
    re_path(
        r"^setting/link-domains/(?P<status>(pending|approved|blocked))/?$",
        views.LinkDomain.as_view(),
        name="settings-link-domain",
    ),
    # pylint: disable=line-too-long
    re_path(
        r"^setting/link-domains/(?P<status>(pending|approved|blocked))/(?P<domain_id>\d+)/?$",
        views.LinkDomain.as_view(),
        name="settings-link-domain",
    ),
    re_path(
        r"^setting/link-domains/(?P<domain_id>\d+)/(?P<status>(pending|approved|blocked))/(?P<report_id>\d+)?$",
        views.update_domain_status,
        name="settings-link-domain-status",
    ),
    re_path(
        r"^settings/ip-blocklist/?$",
        views.IPBlocklist.as_view(),
        name="settings-ip-blocks",
    ),
    re_path(
        r"^settings/ip-blocks/(?P<block_id>\d+)/delete/?$",
        views.IPBlocklist.as_view(),
        name="settings-ip-blocks-delete",
    ),
    # auto-moderation rules
    re_path(r"^settings/automod/?$", views.AutoMod.as_view(), name="settings-automod"),
    re_path(
        r"^settings/automod/(?P<rule_id>\d+)/delete/?$",
        views.automod_delete,
        name="settings-automod-delete",
    ),
    re_path(
        r"^settings/automod/schedule/?$",
        views.schedule_automod_task,
        name="settings-automod-schedule",
    ),
    re_path(
        r"^settings/automod/unschedule/(?P<task_id>\d+)/?$",
        views.unschedule_automod_task,
        name="settings-automod-unschedule",
    ),
    re_path(
        r"^settings/automod/run/?$", views.run_automod, name="settings-automod-run"
    ),
    # moderation
    re_path(
        r"^settings/reports/?$", views.ReportsAdmin.as_view(), name="settings-reports"
    ),
    re_path(
        r"^settings/reports/(?P<report_id>\d+)/?$",
        views.ReportAdmin.as_view(),
        name="settings-report",
    ),
    re_path(
        r"^settings/reports/(?P<user_id>\d+)/suspend/(?P<report_id>\d+)?$",
        views.suspend_user,
        name="settings-report-suspend",
    ),
    re_path(
        r"^settings/reports/(?P<user_id>\d+)/unsuspend/(?P<report_id>\d+)?$",
        views.unsuspend_user,
        name="settings-report-unsuspend",
    ),
    re_path(
        r"^settings/reports/(?P<user_id>\d+)/delete/(?P<report_id>\d+)?$",
        views.moderator_delete_user,
        name="settings-delete-user",
    ),
    re_path(
        r"^settings/reports/(?P<report_id>\d+)/resolve/?$",
        views.resolve_report,
        name="settings-report-resolve",
    ),
    re_path(r"^report/?$", views.Report.as_view(), name="report"),
    re_path(r"^report/(?P<user_id>\d+)/?$", views.Report.as_view(), name="report"),
    re_path(
        r"^report/(?P<user_id>\d+)/status/(?P<status_id>\d+)?$",
        views.Report.as_view(),
        name="report-status",
    ),
    re_path(
        r"^report/link/(?P<link_id>\d+)?$",
        views.Report.as_view(),
        name="report-link",
    ),
    re_path(
        r"^settings/imports/(?P<status>(complete|active))?/?$",
        views.ImportList.as_view(),
        name="settings-imports",
    ),
    re_path(
        r"^settings/imports/(?P<import_id>\d+)/complete/?$",
        views.ImportList.as_view(),
        name="settings-imports-complete",
    ),
    re_path(
        r"^settings/user-imports/(?P<import_id>\d+)/complete/?$",
        views.set_user_import_completed,
        name="settings-user-import-complete",
    ),
    re_path(
        r"^settings/imports/disable/?$",
        views.disable_imports,
        name="settings-imports-disable",
    ),
    re_path(
        r"^settings/imports/enable/?$",
        views.enable_imports,
        name="settings-imports-enable",
    ),
    re_path(
        r"^settings/imports/set-limit/?$",
        views.set_import_size_limit,
        name="settings-imports-set-limit",
    ),
    re_path(
        r"^settings/user-imports/set-limit/?$",
        views.set_user_import_limit,
        name="settings-user-imports-set-limit",
    ),
    re_path(
        r"^settings/celery/?$", views.CeleryStatus.as_view(), name="settings-celery"
    ),
    re_path(
        r"^settings/celery/ping/?$", views.celery_ping, name="settings-celery-ping"
    ),
    re_path(
        r"^settings/email-config/?$",
        views.EmailConfig.as_view(),
        name="settings-email-config",
    ),
    # landing pages
    re_path(r"^about/?$", views.about, name="about"),
    re_path(r"^privacy/?$", views.privacy, name="privacy"),
    re_path(r"^conduct/?$", views.conduct, name="conduct"),
    re_path(r"^impressum/?$", views.impressum, name="impressum"),
    path("", views.Home.as_view(), name="landing"),
    re_path(r"^discover/?$", views.Discover.as_view(), name="discover"),
    re_path(r"^notifications/?$", views.Notifications.as_view(), name="notifications"),
    re_path(
        r"^notifications/(?P<notification_type>mentions)/?$",
        views.Notifications.as_view(),
        name="notifications",
    ),
    re_path(r"^directory/?", views.Directory.as_view(), name="directory"),
    # hashtag
    re_path(
        r"^hashtag/(?P<hashtag_id>\d+)/?$", views.Hashtag.as_view(), name="hashtag"
    ),
    re_path(
        rf"^hashtag/(?P<hashtag_id>\d+){regex.SLUG}/?$",
        views.Hashtag.as_view(),
        name="hashtag",
    ),
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
    re_path(rf"^(?P<tab>{STREAMS})/?$", views.Feed.as_view()),
    re_path(
        r"^direct-messages/?$", views.DirectMessage.as_view(), name="direct-messages"
    ),
    re_path(
        rf"^direct-messages/(?P<username>{regex.USERNAME})/?$",
        views.DirectMessage.as_view(),
        name="direct-messages-user",
    ),
    # search
    re_path(r"^search.json/?$", views.Search.as_view(), name="search"),
    re_path(r"^search/?$", views.Search.as_view(), name="search"),
    # imports
    re_path(r"^import/?$", views.Import.as_view(), name="import"),
    re_path(r"^user-import/?$", views.UserImport.as_view(), name="user-import"),
    re_path(
        r"^import/(?P<job_id>\d+)/?$",
        views.ImportStatus.as_view(),
        name="import-status",
    ),
    re_path(
        r"^import/(?P<job_id>\d+)/stop/?$",
        views.stop_import,
        name="import-stop",
    ),
    re_path(
        r"^import/(?P<job_id>\d+)/retry/(?P<item_id>\d+)/?$",
        views.retry_item,
        name="import-item-retry",
    ),
    re_path(
        r"^import/(?P<job_id>\d+)/failed/?$",
        views.ImportTroubleshoot.as_view(),
        name="import-troubleshoot",
    ),
    re_path(
        r"^import/(?P<job_id>\d+)/review/?$",
        views.ImportManualReview.as_view(),
        name="import-review",
    ),
    re_path(
        r"^import/(?P<job_id>\d+)/review/?$",
        views.ImportManualReview.as_view(),
        name="import-review",
    ),
    re_path(
        r"^import/(?P<job_id>\d+)/review/(?P<item_id>\d+)/approve/?$",
        views.approve_import_item,
        name="import-approve",
    ),
    re_path(
        r"^import/(?P<job_id>\d+)/review/(?P<item_id>\d+)/delete/?$",
        views.delete_import_item,
        name="import-delete",
    ),
    # users
    re_path(rf"{USER_PATH}\.json$", views.User.as_view()),
    re_path(rf"{USER_PATH}/?$", views.User.as_view(), name="user-feed"),
    re_path(rf"^@(?P<username>{regex.USERNAME})$", views.user_redirect),
    re_path(rf"{USER_PATH}/rss/?$", views.rss_feed.RssFeed(), name="user-rss"),
    re_path(
        rf"{USER_PATH}/rss-reviews/?$",
        views.rss_feed.RssReviewsOnlyFeed(),
        name="user-reviews-rss",
    ),
    re_path(
        rf"{USER_PATH}/rss-quotes/?$",
        views.rss_feed.RssQuotesOnlyFeed(),
        name="user-quotes-rss",
    ),
    re_path(
        rf"{USER_PATH}/rss-comments/?$",
        views.rss_feed.RssCommentsOnlyFeed(),
        name="user-comments-rss",
    ),
    re_path(
        rf"{USER_PATH}/(?P<direction>(followers|following))(.json)?/?$",
        views.Relationships.as_view(),
        name="user-relationships",
    ),
    re_path(r"^hide-suggestions/?$", views.hide_suggestions, name="hide-suggestions"),
    re_path(
        rf"{USER_PATH}/reviews-comments",
        views.UserReviewsComments.as_view(),
        name="user-reviews-comments",
    ),
    # groups
    re_path(rf"{USER_PATH}/groups/?$", views.UserGroups.as_view(), name="user-groups"),
    re_path(
        r"^group/(?P<group_id>\d+)(.json)?/?$", views.Group.as_view(), name="group"
    ),
    re_path(
        rf"^group/(?P<group_id>\d+){regex.SLUG}/?$", views.Group.as_view(), name="group"
    ),
    re_path(
        r"^group/delete/(?P<group_id>\d+)/?$", views.delete_group, name="delete-group"
    ),
    re_path(
        r"^group/(?P<group_id>\d+)/add-users/?$",
        views.FindUsers.as_view(),
        name="group-find-users",
    ),
    re_path(r"^add-group-member/?$", views.invite_member, name="invite-group-member"),
    re_path(
        r"^remove-group-member/?$", views.remove_member, name="remove-group-member"
    ),
    re_path(
        r"^accept-group-invitation/?$",
        views.accept_membership,
        name="accept-group-invitation",
    ),
    re_path(
        r"^reject-group-invitation/?$",
        views.reject_membership,
        name="reject-group-invitation",
    ),
    # lists
    re_path(rf"{USER_PATH}/lists/?$", views.UserLists.as_view(), name="user-lists"),
    re_path(r"^list/?$", views.Lists.as_view(), name="lists"),
    re_path(r"^list/saved/?$", views.SavedLists.as_view(), name="saved-lists"),
    re_path(r"^list/(?P<list_id>\d+)(\.json)?/?$", views.List.as_view(), name="list"),
    re_path(
        rf"^list/(?P<list_id>\d+){regex.SLUG}/?$", views.List.as_view(), name="list"
    ),
    re_path(
        r"^list/(?P<list_id>\d+)/item/(?P<list_item>\d+)/?$",
        views.ListItem.as_view(),
        name="list-item",
    ),
    re_path(r"^list/delete/(?P<list_id>\d+)/?$", views.delete_list, name="delete-list"),
    re_path(r"^list/add-book/?$", views.add_book, name="list-add-book"),
    re_path(
        r"^list/(?P<list_id>\d+)/remove/?$",
        views.remove_book,
        name="list-remove-book",
    ),
    re_path(
        r"^list-item/(?P<list_item_id>\d+)/set-position$",
        views.set_book_position,
        name="list-set-book-position",
    ),
    re_path(
        r"^list/(?P<list_id>\d+)/curate/?$", views.Curate.as_view(), name="list-curate"
    ),
    re_path(r"^save-list/(?P<list_id>\d+)/?$", views.save_list, name="list-save"),
    re_path(r"^unsave-list/(?P<list_id>\d+)/?$", views.unsave_list, name="list-unsave"),
    re_path(
        r"^list/(?P<list_id>\d+)/embed/(?P<list_key>[0-9a-f]+)/?$",
        views.unsafe_embed_list,
        name="embed-list",
    ),
    # User books
    re_path(rf"{USER_PATH}/books/?$", views.Shelf.as_view(), name="user-shelves"),
    re_path(
        rf"^{USER_PATH}/(shelf|books)/(?P<shelf_identifier>[\w-]+)(.json)?/?$",
        views.Shelf.as_view(),
        name="shelf",
    ),
    re_path(
        rf"^{LOCAL_USER_PATH}/(books|shelf)/(?P<shelf_identifier>[\w-]+)(.json)?/?$",
        views.Shelf.as_view(),
        name="shelf",
    ),
    re_path(r"^create-shelf/?$", views.create_shelf, name="shelf-create"),
    re_path(r"^delete-shelf/(?P<shelf_id>\d+)/?$", views.delete_shelf),
    re_path(r"^shelve/?$", views.shelve),
    re_path(r"^unshelve/?$", views.unshelve),
    # goals
    re_path(
        rf"{LOCAL_USER_PATH}/goal/(?P<year>\d+)/?$",
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
    re_path(
        r"^preferences/2fa/?$",
        views.Edit2FA.as_view(),
        name="prefs-2fa",
    ),
    re_path(
        r"^preferences/2fa-backup-codes/?$",
        views.GenerateBackupCodes.as_view(),
        name="generate-2fa-backup-codes",
    ),
    re_path(
        r"^preferences/confirm-2fa/?$",
        views.Confirm2FA.as_view(),
        name="conf-2fa",
    ),
    re_path(
        r"^preferences/disable-2fa/?$",
        views.Disable2FA.as_view(),
        name="disable-2fa",
    ),
    re_path(
        r"^2fa-check/?$",
        views.LoginWith2FA.as_view(),
        name="login-with-2fa",
    ),
    re_path(
        r"^2fa-prompt/?$",
        views.Prompt2FA.as_view(),
        name="prompt-2fa",
    ),
    re_path(r"^preferences/export/?$", views.Export.as_view(), name="prefs-export"),
    re_path(
        r"^preferences/user-export/?$",
        views.ExportUser.as_view(),
        name="prefs-user-export",
    ),
    path(
        "preferences/user-export/<archive_id>",
        views.ExportArchive.as_view(),
        name="prefs-export-file",
    ),
    re_path(r"^preferences/move/?$", views.MoveUser.as_view(), name="prefs-move"),
    re_path(r"^preferences/alias/?$", views.AliasUser.as_view(), name="prefs-alias"),
    re_path(
        r"^preferences/remove-alias/?$", views.remove_alias, name="prefs-remove-alias"
    ),
    re_path(r"^preferences/unmove/?$", views.unmove, name="prefs-unmove"),
    re_path(r"^preferences/delete/?$", views.DeleteUser.as_view(), name="prefs-delete"),
    re_path(
        r"^preferences/deactivate/?$",
        views.DeactivateUser.as_view(),
        name="prefs-deactivate",
    ),
    re_path(
        r"^preferences/reactivate/?$",
        views.ReactivateUser.as_view(),
        name="prefs-reactivate",
    ),
    re_path(r"^preferences/block/?$", views.Block.as_view(), name="prefs-block"),
    re_path(r"^block/(?P<user_id>\d+)/?$", views.Block.as_view()),
    re_path(r"^unblock/(?P<user_id>\d+)/?$", views.unblock),
    # statuses
    re_path(rf"{STATUS_PATH}(.json)?/?$", views.Status.as_view(), name="status"),
    re_path(rf"{STATUS_PATH}{regex.SLUG}/?$", views.Status.as_view(), name="status"),
    re_path(rf"{STATUS_PATH}/activity/?$", views.Status.as_view(), name="status"),
    re_path(
        rf"{STATUS_PATH}/replies(.json)?/?$", views.Replies.as_view(), name="replies"
    ),
    re_path(
        r"^edit/(?P<status_id>\d+)/?$", views.EditStatus.as_view(), name="edit-status"
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
        r"^post/(?P<status_type>\w+)/(?P<existing_status_id>\d+)/?$",
        views.CreateStatus.as_view(),
        name="create-status",
    ),
    re_path(
        r"^delete-status/(?P<status_id>\d+)/?(?P<report_id>\d+)?$",
        views.DeleteStatus.as_view(),
        name="delete-status",
    ),
    # interact
    re_path(r"^favorite/(?P<status_id>\d+)/?$", views.Favorite.as_view(), name="fav"),
    re_path(
        r"^unfavorite/(?P<status_id>\d+)/?$", views.Unfavorite.as_view(), name="unfav"
    ),
    re_path(r"^boost/(?P<status_id>\d+)/?$", views.Boost.as_view()),
    re_path(r"^unboost/(?P<status_id>\d+)/?$", views.Unboost.as_view()),
    # books
    re_path(rf"{BOOK_PATH}(.json)?/?$", views.Book.as_view(), name="book"),
    re_path(rf"{BOOK_PATH}{regex.SLUG}/?$", views.Book.as_view(), name="book"),
    re_path(
        r"^series/by/(?P<author_id>\d+)/?$",
        views.BookSeriesBy.as_view(),
        name="book-series-by",
    ),
    re_path(
        rf"{BOOK_PATH}/(?P<user_statuses>review|comment|quote)/?$",
        views.Book.as_view(),
        name="book-user-statuses",
    ),
    re_path(rf"{BOOK_PATH}/edit/?$", views.EditBook.as_view(), name="edit-book"),
    re_path(
        rf"{BOOK_PATH}/confirm/?$",
        views.ConfirmEditBook.as_view(),
        name="edit-book-confirm",
    ),
    re_path(
        r"^create-book/data/?$", views.create_book_from_data, name="create-book-data"
    ),
    re_path(r"^create-book/?$", views.CreateBook.as_view(), name="create-book"),
    re_path(
        r"^create-book/confirm/?$",
        views.ConfirmEditBook.as_view(),
        name="create-book-confirm",
    ),
    re_path(rf"{BOOK_PATH}/editions(.json)?/?$", views.Editions.as_view()),
    re_path(
        r"^upload-cover/(?P<book_id>\d+)/?$", views.upload_cover, name="upload-cover"
    ),
    re_path(
        r"^add-description/(?P<book_id>\d+)/?$",
        views.add_description,
        name="add-description",
    ),
    re_path(
        rf"{BOOK_PATH}/filelink/?$", views.BookFileLinks.as_view(), name="file-link"
    ),
    re_path(
        rf"{BOOK_PATH}/filelink/(?P<link_id>\d+)/?$",
        views.BookFileLinks.as_view(),
        name="file-link",
    ),
    re_path(
        rf"{BOOK_PATH}/filelink/(?P<link_id>\d+)/delete/?$",
        views.delete_link,
        name="file-link-delete",
    ),
    re_path(
        rf"{BOOK_PATH}/filelink/add/?$",
        views.AddFileLink.as_view(),
        name="file-link-add",
    ),
    re_path(r"^resolve-book/?$", views.resolve_book, name="resolve-book"),
    re_path(r"^switch-edition/?$", views.switch_edition, name="switch-edition"),
    re_path(
        rf"{BOOK_PATH}/update/(?P<connector_identifier>[\w\.]+)/?$",
        views.update_book_from_remote,
        name="book-update-remote",
    ),
    re_path(
        r"^author/(?P<author_id>\d+)/update/(?P<connector_identifier>[\w\.]+)/?$",
        views.update_author_from_remote,
        name="author-update-remote",
    ),
    # isbn
    re_path(r"^isbn/(?P<isbn>[\dxX]+)(.json)?/?$", views.Isbn.as_view()),
    # author
    re_path(
        r"^author/(?P<author_id>\d+)(.json)?/?$", views.Author.as_view(), name="author"
    ),
    re_path(
        rf"^author/(?P<author_id>\d+){regex.SLUG}/?$",
        views.Author.as_view(),
        name="author",
    ),
    re_path(
        r"^author/(?P<author_id>\d+)/edit/?$",
        views.EditAuthor.as_view(),
        name="edit-author",
    ),
    # reading progress
    re_path(r"^edit-readthrough/?$", views.edit_readthrough, name="edit-readthrough"),
    re_path(r"^delete-readthrough/?$", views.delete_readthrough),
    re_path(
        r"^create-readthrough/?$",
        views.ReadThrough.as_view(),
        name="create-readthrough",
    ),
    re_path(r"^delete-progressupdate/?$", views.delete_progressupdate),
    # shelve actions
    re_path(
        r"^reading-status/update/(?P<book_id>\d+)/?$",
        views.update_progress,
        name="reading-status-update",
    ),
    re_path(
        r"^reading-status/(?P<status>want|start|finish|stop)/(?P<book_id>\d+)/?$",
        views.ReadingStatus.as_view(),
        name="reading-status",
    ),
    # following
    re_path(r"^follow/?$", views.follow, name="follow"),
    re_path(r"^unfollow/?$", views.unfollow, name="unfollow"),
    re_path(
        r"^remove-follow/(?P<user_id>\d+)/?$", views.remove_follow, name="remove-follow"
    ),
    re_path(r"^accept-follow-request/?$", views.accept_follow_request),
    re_path(r"^delete-follow-request/?$", views.delete_follow_request),
    re_path(r"^ostatus_follow/?$", views.remote_follow, name="remote-follow"),
    re_path(r"^remote_follow/?$", views.remote_follow_page, name="remote-follow-page"),
    re_path(
        r"^ostatus_success/?$", views.ostatus_follow_success, name="ostatus-success"
    ),
    # annual summary
    re_path(
        r"^my-year-in-the-books/(?P<year>\d+)/?$",
        views.personal_annual_summary,
    ),
    re_path(
        rf"{LOCAL_USER_PATH}/(?P<year>\d+)-in-the-books/?$",
        views.AnnualSummary.as_view(),
        name="annual-summary",
    ),
    re_path(r"^summary_add_key/?$", views.summary_add_key, name="summary-add-key"),
    re_path(
        r"^summary_revoke_key/?$", views.summary_revoke_key, name="summary-revoke-key"
    ),
    path("guided-tour/<tour>", views.toggle_guided_tour),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serves /static when DEBUG is true.
urlpatterns.extend(staticfiles_urlpatterns())

# pylint: disable=invalid-name
handler500 = "bookwyrm.views.server_error"

# pylint: disable=invalid-name
handler403 = "bookwyrm.views.permission_denied"
