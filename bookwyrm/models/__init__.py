""" bring all the models into the app namespace """
import inspect
import sys

from .book import Book, Work, Edition, BookDataModel
from .author import Author
from .connector import Connector

from .shelf import Shelf, ShelfBook
from .list import List, ListItem

from .status import Status, GeneratedNote, Comment, Quotation
from .status import Review, ReviewRating
from .status import Boost
from .attachment import Image
from .favorite import Favorite
from .notification import Notification
from .readthrough import ReadThrough, ProgressUpdate, ProgressMode

from .user import User, KeyPair, AnnualGoal
from .relationship import UserFollows, UserFollowRequest, UserBlocks
from .report import Report, ReportComment
from .federated_server import FederatedServer

from .import_job import ImportJob, ImportItem

from .site import SiteSettings, SiteInvite, PasswordReset, InviteRequest
from .announcement import Announcement

cls_members = inspect.getmembers(sys.modules[__name__], inspect.isclass)
activity_models = {
    c[1].activity_serializer.__name__: c[1]
    for c in cls_members
    if hasattr(c[1], "activity_serializer")
}

status_models = [
    c.__name__ for (_, c) in activity_models.items() if issubclass(c, Status)
]
