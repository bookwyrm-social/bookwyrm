''' note serializer and children thereof '''
from dataclasses import dataclass, field
from typing import Dict, List

from .base_activity import ActivityObject, Image, Link

@dataclass(init=False)
class Tombstone(ActivityObject):
    ''' the placeholder for a deleted status '''
    url: str
    published: str
    deleted: str
    type: str = 'Tombstone'


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
    tag: List[Link] = field(default=lambda: [])
    attachment: List[Image] = field(default=lambda: [])
    sensitive: bool = False
    type: str = 'Note'


@dataclass(init=False)
class Article(Note):
    ''' what's an article except a note with more fields '''
    name: str
    type: str = 'Article'


@dataclass(init=False)
class GeneratedNote(Note):
    ''' just a re-typed note '''
    type: str = 'GeneratedNote'


@dataclass(init=False)
class Comment(Note):
    ''' like a note but with a book '''
    inReplyToBook: str
    type: str = 'Comment'


@dataclass(init=False)
class Review(Comment):
    ''' a full book review '''
    name: str
    rating: int
    type: str = 'Review'


@dataclass(init=False)
class Quotation(Comment):
    ''' a quote and commentary on a book '''
    quote: str
    type: str = 'Quotation'

@dataclass(init=False)
class Progress(Comment):
    ''' a progress update on a book '''
    quote: str
    type: str = 'Progress'
