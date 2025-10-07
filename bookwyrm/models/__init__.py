""" bring all the models into the app namespace """
import inspect
import sys

from .book import Book, Work, Edition, BookDataModel
from .author import Author
from .link import Link, FileLink, LinkDomain
from .connector import Connector

from .shelf import Shelf, ShelfBook
from .list import List, ListItem

from .status import Status, GeneratedNote, Comment, Quotation
from .status import Review, ReviewRating
from .status import Boost
from .attachment import Image
from .favorite import Favorite
from .readthrough import ReadThrough, ProgressUpdate, ProgressMode

from .user import User, KeyPair
from .annual_goal import AnnualGoal
from .relationship import UserFollows, UserFollowRequest, UserBlocks
from .report import Report, ReportAction
from .federated_server import FederatedServer

from .group import Group, GroupMember, GroupMemberInvitation

from .housekeeping import CleanUpUserExportFilesJob, start_export_deletions

from .import_job import ImportJob, ImportItem
from .bookwyrm_import_job import (
    BookwyrmImportJob,
    UserImportBook,
    UserImportPost,
    import_book_task,
)
from .bookwyrm_export_job import BookwyrmExportJob

from .move import MoveUser

from .site import SiteSettings, Theme, SiteInvite
from .site import PasswordReset, InviteRequest
from .announcement import Announcement
from .antispam import EmailBlocklist, IPBlocklist, AutoMod, automod_task

from .notification import Notification, NotificationType

from .hashtag import Hashtag

from .session import UserSession, create_user_session

cls_members = inspect.getmembers(sys.modules[__name__], inspect.isclass)
activity_models = {
    c[1].activity_serializer.__name__: c[1]
    for c in cls_members
    if hasattr(c[1], "activity_serializer")
}

status_models = [
    c.__name__ for (_, c) in activity_models.items() if issubclass(c, Status)
]
