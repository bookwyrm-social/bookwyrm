''' note serializer '''
from dataclasses import dataclass, field
from typing import Dict, List

from .base_activity import ActivityObject, Image

@dataclass(init=False)
class Note(ActivityObject):
    ''' Note activity '''
    url: str
    inReplyTo: str
    published: str
    attributedTo: str
    to: List[str]
    cc: List[str]
    content: str
    replies: Dict
    # TODO: this is wrong???
    attachment: List[Image] = field(default=lambda: [])
    sensitive: bool = False


@dataclass(init=False)
class Article(Note):
    ''' what's an article except a note with more fields '''
    name: str


@dataclass(init=False)
class Comment(Note):
    ''' like a note but with a book '''
    inReplyToBook: str


@dataclass(init=False)
class Review(Comment):
    ''' a full book review '''
    name: str
    rating: int


@dataclass(init=False)
class Quotation(Comment):
    ''' a quote and commentary on a book '''
    quote: str


@dataclass(init=False)
class Like(ActivityObject):
    actor: str
    object: str
