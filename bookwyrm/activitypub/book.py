''' book and author data '''
from dataclasses import dataclass, field
from typing import List

from .base_activity import ActivityObject, Image

@dataclass(init=False)
class Book(ActivityObject):
    ''' serializes an edition or work, abstract '''
    title: str
    sortTitle: str = ''
    subtitle: str = ''
    description: str = ''
    languages: List[str]
    series: str = ''
    seriesNumber: str = ''
    subjects: List[str]
    subjectPlaces: List[str]

    authors: List[str]
    firstPublishedDate: str = ''
    publishedDate: str = ''

    openlibraryKey: str = ''
    librarythingKey: str = ''
    goodreadsKey: str = ''

    attachment: List[Image] = field(default_factory=lambda: [])
    type: str = 'Book'


@dataclass(init=False)
class Edition(Book):
    ''' Edition instance of a book object '''
    isbn10: str
    isbn13: str
    oclcNumber: str
    asin: str
    pages: str
    physicalFormat: str
    publishers: List[str]

    work: str
    type: str = 'Edition'


@dataclass(init=False)
class Work(Book):
    ''' work instance of a book object '''
    lccn: str
    editions: List[str]
    type: str = 'Work'


@dataclass(init=False)
class Author(ActivityObject):
    ''' author of a book '''
    name: str
    born: str = ''
    died: str = ''
    aliases: str = ''
    bio: str = ''
    openlibraryKey: str = ''
    wikipediaLink: str = ''
    type: str = 'Person'
