""" book and author data """
from dataclasses import dataclass, field
from typing import List, Optional

from .base_activity import ActivityObject
from .image import Document


# pylint: disable=invalid-name
@dataclass(init=False)
class BookData(ActivityObject):
    """shared fields for all book data and authors"""

    openlibraryKey: Optional[str] = None
    inventaireId: Optional[str] = None
    librarythingKey: Optional[str] = None
    goodreadsKey: Optional[str] = None
    bnfId: Optional[str] = None
    viaf: Optional[str] = None
    wikidata: Optional[str] = None
    asin: Optional[str] = None
    aasin: Optional[str] = None
    isfdb: Optional[str] = None
    lastEditedBy: Optional[str] = None
    links: List[str] = field(default_factory=lambda: [])
    fileLinks: List[str] = field(default_factory=lambda: [])


# pylint: disable=invalid-name
@dataclass(init=False)
class Book(BookData):
    """serializes an edition or work, abstract"""

    title: str
    sortTitle: Optional[str] = None
    subtitle: Optional[str] = None
    description: str = ""
    languages: List[str] = field(default_factory=lambda: [])
    series: str = ""
    seriesNumber: str = ""
    subjects: List[str] = field(default_factory=lambda: [])
    subjectPlaces: List[str] = field(default_factory=lambda: [])

    authors: List[str] = field(default_factory=lambda: [])
    firstPublishedDate: str = ""
    publishedDate: str = ""

    cover: Optional[Document] = None
    type: str = "Book"


# pylint: disable=invalid-name
@dataclass(init=False)
class Edition(Book):
    """Edition instance of a book object"""

    work: str
    isbn10: str = ""
    isbn13: str = ""
    oclcNumber: str = ""
    pages: Optional[int] = None
    physicalFormat: str = ""
    physicalFormatDetail: str = ""
    publishers: List[str] = field(default_factory=lambda: [])
    editionRank: int = 0

    type: str = "Edition"


# pylint: disable=invalid-name
@dataclass(init=False)
class Work(Book):
    """work instance of a book object"""

    lccn: str = ""
    editions: List[str] = field(default_factory=lambda: [])
    type: str = "Work"


# pylint: disable=invalid-name
@dataclass(init=False)
class Author(BookData):
    """author of a book"""

    name: str
    isni: Optional[str] = None
    viafId: Optional[str] = None
    gutenbergId: Optional[str] = None
    born: Optional[str] = None
    died: Optional[str] = None
    aliases: List[str] = field(default_factory=lambda: [])
    bio: str = ""
    wikipediaLink: str = ""
    type: str = "Author"
    website: str = ""
