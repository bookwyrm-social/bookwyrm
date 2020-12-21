''' book and author data '''
from dataclasses import dataclass, field
from typing import List

from .base_activity import ActivityObject
from .image import Image

@dataclass(init=False)
class Book(ActivityObject):
    ''' serializes an edition or work, abstract '''
    title: str
    sortTitle: str = ''
    subtitle: str = ''
    description: str = ''
    languages: List[str] = field(default_factory=lambda: [])
    series: str = ''
    seriesNumber: str = ''
    subjects: List[str] = field(default_factory=lambda: [])
    subjectPlaces: List[str] = field(default_factory=lambda: [])

    authors: List[str] = field(default_factory=lambda: [])
    firstPublishedDate: str = ''
    publishedDate: str = ''

    openlibraryKey: str = ''
    librarythingKey: str = ''
    goodreadsKey: str = ''

    cover: Image = field(default_factory=lambda: {})
    type: str = 'Book'


@dataclass(init=False)
class Edition(Book):
    ''' Edition instance of a book object '''
    work: str
    isbn10: str = ''
    isbn13: str = ''
    oclcNumber: str = ''
    asin: str = ''
    pages: int = None
    physicalFormat: str = ''
    publishers: List[str] = field(default_factory=lambda: [])

    type: str = 'Edition'


@dataclass(init=False)
class Work(Book):
    ''' work instance of a book object '''
    lccn: str = ''
    defaultEdition: str = ''
    editions: List[str] = field(default_factory=lambda: [])
    type: str = 'Work'


@dataclass(init=False)
class Author(ActivityObject):
    ''' author of a book '''
    name: str
    born: str = None
    died: str = None
    aliases: List[str] = field(default_factory=lambda: [])
    bio: str = ''
    openlibraryKey: str = ''
    wikipediaLink: str = ''
    type: str = 'Person'
