""" make sure all our nice views are available """
# site admin
from .admin.announcements import Announcements, Announcement, delete_announcement
from .admin.dashboard import Dashboard
from .admin.federation import Federation, FederatedServer
from .admin.federation import AddFederatedServer, ImportServerBlocklist
from .admin.federation import block_server, unblock_server
from .admin.email_blocklist import EmailBlocklist
from .admin.ip_blocklist import IPBlocklist
from .admin.invite import ManageInvites, Invite, InviteRequest
from .admin.invite import ManageInviteRequests, ignore_invite_request
from .admin.link_domains import LinkDomain, update_domain_status
from .admin.reports import (
    ReportAdmin,
    ReportsAdmin,
    resolve_report,
    suspend_user,
    unsuspend_user,
    moderator_delete_user,
)
from .admin.site import Site
from .admin.user_admin import UserAdmin, UserAdminList

# user preferences
from .preferences.change_password import ChangePassword
from .preferences.edit_user import EditUser
from .preferences.delete_user import DeleteUser
from .preferences.block import Block, unblock

# books
from .books.books import (
    Book,
    upload_cover,
    add_description,
    resolve_book,
)
from .books.books import update_book_from_remote
from .books.edit_book import EditBook, ConfirmEditBook
from .books.editions import Editions, switch_edition
from .books.links import BookFileLinks, AddFileLink, delete_link

# landing
from .landing.about import about, privacy, conduct
from .landing.landing import Home, Landing
from .landing.login import Login, Logout
from .landing.register import Register, ConfirmEmail, ConfirmEmailCode, resend_link
from .landing.password import PasswordResetRequest, PasswordReset

# shelves
from .shelf.shelf import Shelf
from .shelf.shelf_actions import create_shelf, delete_shelf
from .shelf.shelf_actions import shelve, unshelve

# csv import
from .imports.import_data import Import
from .imports.import_status import ImportStatus, retry_item
from .imports.troubleshoot import ImportTroubleshoot
from .imports.manually_review import (
    ImportManualReview,
    approve_import_item,
    delete_import_item,
)

# misc views
from .author import Author, EditAuthor, update_author_from_remote
from .directory import Directory
from .discover import Discover
from .feed import DirectMessage, Feed, Replies, Status
from .follow import (
    follow,
    unfollow,
    ostatus_follow_request,
    ostatus_follow_success,
    remote_follow,
    remote_follow_page,
)
from .follow import accept_follow_request, delete_follow_request
from .get_started import GetStartedBooks, GetStartedProfile, GetStartedUsers
from .goal import Goal, hide_goal
from .group import (
    Group,
    UserGroups,
    FindUsers,
    delete_group,
    invite_member,
    remove_member,
    accept_membership,
    reject_membership,
)
from .inbox import Inbox
from .interaction import Favorite, Unfavorite, Boost, Unboost
from .isbn import Isbn
from .list import Lists, SavedLists, List, Curate, UserLists
from .list import save_list, unsave_list, delete_list, unsafe_embed_list
from .notifications import Notifications
from .outbox import Outbox
from .reading import ReadThrough, delete_readthrough, delete_progressupdate
from .reading import ReadingStatus
from .report import Report
from .rss_feed import RssFeed
from .search import Search
from .status import CreateStatus, EditStatus, DeleteStatus, update_progress
from .status import edit_readthrough
from .updates import get_notification_count, get_unread_status_count
from .user import User, Followers, Following, hide_suggestions, user_redirect
from .wellknown import *
from .annual_summary import (
    AnnualSummary,
    personal_annual_summary,
    summary_add_key,
    summary_revoke_key,
)
