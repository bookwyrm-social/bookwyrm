''' make sure all our nice views are available '''
from .authentication import Login, Register, Logout
from .author import Author, EditAuthor
from .books import Book, EditBook, Editions
from .books import upload_cover, add_description, switch_edition, resolve_book
from .direct_message import DirectMessage
from .error import not_found_page, server_error_page
from .follow import follow, unfollow
from .follow import accept_follow_request, delete_follow_request
from .import_data import Import, ImportStatus
from .interaction import Favorite, Unfavorite, Boost, Unboost
from .invite import ManageInvites, Invite
from .landing import About, Home, Feed, Discover
from .notifications import Notifications
from .reading import edit_readthrough, create_readthrough, delete_readthrough
from .reading import start_reading, finish_reading
from .password import PasswordResetRequest, PasswordReset, ChangePassword
from .tag import Tag, AddTag, RemoveTag
from .search import Search
from .shelf import Shelf
from .shelf import user_shelves_page, create_shelf, delete_shelf
from .shelf import shelve, unshelve
from .status import Status, Replies, CreateStatus, DeleteStatus
from .user import User, EditUser, Followers, Following
