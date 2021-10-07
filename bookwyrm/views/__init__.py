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
from .admin.reports import (
    Report,
    Reports,
    make_report,
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
from .books.books import Book, upload_cover, add_description, resolve_book
from .books.edit_book import EditBook, ConfirmEditBook
from .books.editions import Editions, switch_edition

# misc views
from .author import Author, EditAuthor
from .directory import Directory
from .discover import Discover
from .feed import DirectMessage, Feed, Replies, Status
from .follow import follow, unfollow
from .follow import accept_follow_request, delete_follow_request
from .get_started import GetStartedBooks, GetStartedProfile, GetStartedUsers
from .goal import Goal, hide_goal
from .import_data import Import, ImportStatus
from .inbox import Inbox
from .interaction import Favorite, Unfavorite, Boost, Unboost
from .isbn import Isbn
from .landing import About, Home, Landing
from .list import Lists, SavedLists, List, Curate, UserLists
from .list import save_list, unsave_list, delete_list
from .login import Login, Logout
from .notifications import Notifications
from .outbox import Outbox
from .reading import create_readthrough, delete_readthrough, delete_progressupdate
from .reading import ReadingStatus
from .register import Register, ConfirmEmail, ConfirmEmailCode, resend_link
from .rss_feed import RssFeed
from .password import PasswordResetRequest, PasswordReset
from .search import Search
from .shelf import Shelf
from .shelf import create_shelf, delete_shelf
from .shelf import shelve, unshelve
from .status import CreateStatus, DeleteStatus, DeleteAndRedraft, update_progress
from .status import edit_readthrough
from .updates import get_notification_count, get_unread_status_count
from .user import User, Followers, Following, hide_suggestions
from .wellknown import *
