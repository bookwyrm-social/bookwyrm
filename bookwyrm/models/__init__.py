''' bring all the models into the app namespace '''
import inspect
import sys

from .book import Book, Work, Edition, BookDataModel
from .author import Author
from .connector import Connector

from .shelf import Shelf, ShelfBook

from .status import Status, GeneratedNote, Review, Comment, Quotation
from .status import Favorite, Boost, Notification, ReadThrough
from .attachment import Image

from .tag import Tag, UserTag

from .user import User, KeyPair
from .relationship import UserFollows, UserFollowRequest, UserBlocks
from .federated_server import FederatedServer

from .import_job import ImportJob, ImportItem

from .site import SiteSettings, SiteInvite, PasswordReset

cls_members = inspect.getmembers(sys.modules[__name__], inspect.isclass)
activity_models = {c[1].activity_serializer.__name__: c[1] \
    for c in cls_members if hasattr(c[1], 'activity_serializer')}

status_models = [
    c.__name__ for (_, c) in activity_models.items() if issubclass(c, Status)]
