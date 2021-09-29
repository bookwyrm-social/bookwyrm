""" note serializer and children thereof """
from dataclasses import dataclass, field
from typing import Dict, List
from django.apps import apps

from .base_activity import ActivityObject, Link
from .image import Document


@dataclass(init=False)
class Tombstone(ActivityObject):
    """the placeholder for a deleted status"""

    def to_model(self, *args, **kwargs):  # pylint: disable=unused-argument
        """this should never really get serialized, just searched for"""
        model = apps.get_model("bookwyrm.Status")
        return model.find_existing_by_remote_id(self.id)


# pylint: disable=invalid-name
@dataclass(init=False)
class Note(ActivityObject):
    """Note activity"""

    published: str
    attributedTo: str
    content: str = ""
    to: List[str] = field(default_factory=lambda: [])
    cc: List[str] = field(default_factory=lambda: [])
    replies: Dict = field(default_factory=lambda: {})
    inReplyTo: str = None
    summary: str = None
    tag: List[Link] = field(default_factory=lambda: [])
    attachment: List[Document] = field(default_factory=lambda: [])
    sensitive: bool = False


@dataclass(init=False)
class Article(Note):
    """what's an article except a note with more fields"""

    name: str


@dataclass(init=False)
class GeneratedNote(Note):
    """just a re-typed note"""


# pylint: disable=invalid-name
@dataclass(init=False)
class Comment(Note):
    """like a note but with a book"""

    inReplyToBook: str
    readingStatus: str = None
    progress: int = None
    progressMode: str = None


@dataclass(init=False)
class Quotation(Comment):
    """a quote and commentary on a book"""

    quote: str
    position: int = None
    positionMode: str = None


@dataclass(init=False)
class Review(Comment):
    """a full book review"""

    name: str = None
    rating: int = None


@dataclass(init=False)
class Rating(Comment):
    """just a star rating"""

    rating: int
    content: str = None
    name: str = None  # not used, but the model inherits from Review
