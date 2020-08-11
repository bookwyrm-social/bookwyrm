''' bring activitypub functions into the namespace '''
import inspect
import sys

from .base_activity import ActivityEncoder, Image, PublicKey
from .note import Note, Article, Comment, Review, Quotation, Like
from .person import Person
from .outbox import Outbox, OutboxPage

from .book import Edition, Work, Author

from .book import get_shelf
from .create import get_create, get_update
from .follow import get_following, get_followers
from .follow import get_follow_request, get_unfollow, get_accept, get_reject
from .shelve import get_add, get_remove
from .status import get_rating_note
from .status import get_replies_page
from .status import get_favorite, get_unfavorite
from .status import get_boost
from .status import get_add_tag, get_remove_tag

# this creates a list of all the Activity types that we can serialize,
# so when an Activity comes in from outside, we can check if it's known
cls_members = inspect.getmembers(sys.modules[__name__], inspect.isclass)
activity_objects = {c[0]: c[1] for c in cls_members \
    if hasattr(c[1], 'to_model')}
