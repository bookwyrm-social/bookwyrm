""" book and author data """
from dataclasses import dataclass, field
from typing import List

from .base_activity import ActivityObject
from .image import Document


@dataclass(init=False)
class BookData(ActivityObject):
    """shared fields for all book data and authors"""

    openlibraryKey: str = None
    inventaireId: str = None
    librarythingKey: str = None
    goodreadsKey: str = None
    bnfId: str = None
    lastEditedBy: str = None


@dataclass(init=False)
class Book(BookData):
    """serializes an edition or work, abstract"""

    title: str
    sortTitle: str = ""
    subtitle: str = ""
    description: str = ""
    languages: List[str] = field(default_factory=lambda: [])
    series: str = ""
    seriesNumber: str = ""
    subjects: List[str] = field(default_factory=lambda: [])
    subjectPlaces: List[str] = field(default_factory=lambda: [])

    authors: List[str] = field(default_factory=lambda: [])
    firstPublishedDate: str = ""
    publishedDate: str = ""

    cover: Document = None
    type: str = "Book"


@dataclass(init=False)
class Edition(Book):
    """Edition instance of a book object"""

    work: str
    isbn10: str = ""
    isbn13: str = ""
    oclcNumber: str = ""
    asin: str = ""
    pages: int = None
    physicalFormat: str = ""
    publishers: List[str] = field(default_factory=lambda: [])
    editionRank: int = 0

    type: str = "Edition"


@dataclass(init=False)
class Work(Book):
    """work instance of a book object"""

    lccn: str = ""
    editions: List[str] = field(default_factory=lambda: [])
    type: str = "Work"


@dataclass(init=False)
class Author(BookData):
    """author of a book"""

    name: str
    isni: str = None
    viafId: str = None
    gutenbergId: str = None
    born: str = None
    died: str = None
    aliases: List[str] = field(default_factory=lambda: [])
    bio: str = ""
    wikipediaLink: str = ""
    type: str = "Author"
