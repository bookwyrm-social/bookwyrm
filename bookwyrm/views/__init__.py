''' make sure all our nice views are available '''
from .authentication import Login, Register, Logout
from .password import PasswordResetRequest, PasswordReset, ChangePassword
from .invite import ManageInvites, Invite
from .landing import About, Home, Feed, Discover
from .notifications import Notifications
from .direct_message import DirectMessage
from .import_data import Import, ImportStatus
from .user import User, EditUser, Followers, Following
from .status import Status, Replies, CreateStatus, DeleteStatus
from .interaction import Favorite, Unfavorite, Boost, Unboost
from .books import Book, EditBook, Editions
from .books import upload_cover, add_description, switch_edition, resolve_book
from .author import Author, EditAuthor
from .tag import Tag, AddTag, RemoveTag
from .shelf import Shelf
from .shelf import user_shelves_page, create_shelf, delete_shelf
from .shelf import shelve, unshelve
from .search import Search
