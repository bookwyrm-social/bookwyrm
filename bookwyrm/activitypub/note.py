""" note serializer and children thereof """
from dataclasses import dataclass, field
from typing import Dict, List
import re

from django.apps import apps
from django.db import IntegrityError, transaction

from .base_activity import ActivityObject, ActivitySerializerError, Link
from .image import Document


@dataclass(init=False)
class Tombstone(ActivityObject):
    """the placeholder for a deleted status"""

    type: str = "Tombstone"

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
    updated: str = None
    type: str = "Note"

    # pylint: disable=too-many-arguments
    def to_model(
        self,
        model=None,
        instance=None,
        allow_create=True,
        save=True,
        overwrite=True,
        allow_external_connections=True,
        trigger=None,
    ):
        instance = super().to_model(
            model, instance, allow_create, save, overwrite, allow_external_connections
        )

        if instance is None:
            return instance

        # Replace links to hashtags in content with local URLs
        changed_content = False
        for hashtag in instance.mention_hashtags.all():
            updated_content = re.sub(
                rf'(<a href=")[^"]*(" data-mention="hashtag">{hashtag.name}</a>)',
                rf"\1{hashtag.remote_id}\2",
                instance.content,
                flags=re.IGNORECASE,
            )
            if instance.content != updated_content:
                instance.content = updated_content
                changed_content = True

        if not save or not changed_content:
            return instance

        with transaction.atomic():
            try:
                instance.save(broadcast=False, update_fields=["content"])
            except IntegrityError as e:
                raise ActivitySerializerError(e)

        return instance


@dataclass(init=False)
class Article(Note):
    """what's an article except a note with more fields"""

    name: str
    type: str = "Article"


@dataclass(init=False)
class GeneratedNote(Note):
    """just a re-typed note"""

    type: str = "GeneratedNote"


# pylint: disable=invalid-name
@dataclass(init=False)
class Comment(Note):
    """like a note but with a book"""

    inReplyToBook: str
    readingStatus: str = None
    progress: int = None
    progressMode: str = None
    type: str = "Comment"


@dataclass(init=False)
class Quotation(Comment):
    """a quote and commentary on a book"""

    quote: str
    position: int = None
    positionMode: str = None
    type: str = "Quotation"


@dataclass(init=False)
class Review(Comment):
    """a full book review"""

    name: str = None
    rating: int = None
    type: str = "Review"


@dataclass(init=False)
class Rating(Comment):
    """just a star rating"""

    rating: int
    content: str = None
    name: str = None  # not used, but the model inherits from Review
    type: str = "Rating"
