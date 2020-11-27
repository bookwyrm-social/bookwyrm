''' book and author data '''
from dataclasses import dataclass, field
from typing import List

from .base_activity import ActivityObject, Image

@dataclass(init=False)
class Book(ActivityObject):
    ''' serializes an edition or work, abstract '''
    authors: List[str]
    first_published_date: str
    published_date: str

    title: str
    sort_title: str
    subtitle: str
    description: str
    languages: List[str]
    series: str
    series_number: str
    subjects: List[str]
    subject_places: List[str]

    openlibrary_key: str
    librarything_key: str
    goodreads_key: str

    attachment: List[Image] = field(default_factory=lambda: [])
    type: str = 'Book'


@dataclass(init=False)
class Edition(Book):
    ''' Edition instance of a book object '''
    isbn_10: str
    isbn_13: str
    oclc_number: str
    asin: str
    pages: str
    physical_format: str
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
