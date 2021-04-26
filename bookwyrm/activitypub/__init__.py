""" bring activitypub functions into the namespace """
import inspect
import sys

from .base_activity import ActivityEncoder, Signature, naive_parse
from .base_activity import Link, Mention
from .base_activity import ActivitySerializerError, resolve_remote_id
from .image import Document, Image
from .note import Note, GeneratedNote, Article, Comment, Quotation
from .note import Review, Rating
from .note import Tombstone
from .ordered_collection import OrderedCollection, OrderedCollectionPage
from .ordered_collection import CollectionItem, ListItem, ShelfItem
from .ordered_collection import BookList, Shelf
from .person import Person, PublicKey
from .response import ActivitypubResponse
from .book import Edition, Work, Author
from .verbs import Create, Delete, Undo, Update
from .verbs import Follow, Accept, Reject, Block
from .verbs import Add, Remove
from .verbs import Announce, Like

# this creates a list of all the Activity types that we can serialize,
# so when an Activity comes in from outside, we can check if it's known
cls_members = inspect.getmembers(sys.modules[__name__], inspect.isclass)
activity_objects = {c[0]: c[1] for c in cls_members if hasattr(c[1], "to_model")}


def parse(activity_json):
    """figure out what activity this is and parse it"""
    return naive_parse(activity_objects, activity_json)
