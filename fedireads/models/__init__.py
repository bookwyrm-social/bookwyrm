''' bring all the models into the app namespace '''
import inspect
import sys

from .book import Connector, Book, Work, Edition, Author
from .shelf import Shelf, ShelfBook
from .status import Status, Review, Comment, Quotation
from .status import Favorite, Boost, Tag, Notification, ReadThrough
from .user import User, UserFollows, UserFollowRequest, UserBlocks
from .user import FederatedServer

from .import_job import ImportJob, ImportItem
from .site import SiteSettings, SiteInvite

cls_members = inspect.getmembers(sys.modules[__name__], inspect.isclass)
activity_models = {c[0]: c[1].activity_serializer for c in cls_members \
    if hasattr(c[1], 'activity_serializer')}
