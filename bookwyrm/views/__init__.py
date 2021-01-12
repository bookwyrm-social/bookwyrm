''' make sure all our nice views are available '''
from .authentication import Login, Register, Logout
from .password import PasswordResetRequest, PasswordReset, ChangePassword
from .invite import ManageInvites, Invite
