''' make sure all our nice views are available '''
from .authentication import Login, Register, Logout
from .password import PasswordResetRequest, PasswordReset, ChangePassword
from .invite import ManageInvites, Invite
from .landing import About, Home, Feed, Discover
from .notifications import Notifications
from .direct_message import DirectMessage
from .import_data import Import, ImportStatus
from .user import User, EditUser, Followers, Following
