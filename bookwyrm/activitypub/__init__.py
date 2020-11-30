''' bring activitypub functions into the namespace '''
import inspect
import sys

from .base_activity import ActivityEncoder, Signature
from .base_activity import Link, Mention
from .base_activity import ActivitySerializerError, resolve_remote_id
from .image import Image
from .note import Note, GeneratedNote, Article, Comment, Review, Quotation
from .note import Tombstone
from .interaction import Boost, Like
from .ordered_collection import OrderedCollection, OrderedCollectionPage
from .person import Person, PublicKey
from .book import Edition, Work, Author
from .verbs import Create, Delete, Undo, Update
from .verbs import Follow, Accept, Reject
from .verbs import Add, AddBook, Remove

# this creates a list of all the Activity types that we can serialize,
# so when an Activity comes in from outside, we can check if it's known
cls_members = inspect.getmembers(sys.modules[__name__], inspect.isclass)
activity_objects = {c[0]: c[1] for c in cls_members \
    if hasattr(c[1], 'to_model')}
