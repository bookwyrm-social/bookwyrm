''' bring all the models into the app namespace '''
import inspect
import sys

from .book import Book, Work, Edition, Author
from .connector import Connector
from .relationship import UserFollows, UserFollowRequest, UserBlocks
from .shelf import Shelf, ShelfBook
from .status import Status, GeneratedStatus, Review, Comment, Quotation
from .status import Favorite, Boost, Notification, ReadThrough
from .tag import Tag
from .user import User
from .federated_server import FederatedServer

from .import_job import ImportJob, ImportItem
from .site import SiteSettings, SiteInvite, PasswordReset

cls_members = inspect.getmembers(sys.modules[__name__], inspect.isclass)
activity_models = {c[0]: c[1].activity_serializer for c in cls_members \
    if hasattr(c[1], 'activity_serializer')}
