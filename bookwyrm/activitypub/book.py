""" book and author data """
from dataclasses import dataclass, field
from typing import Optional

from .base_activity import ActivityObject
from .image import Document
from .ordered_collection import CollectionItem, OrderedCollection


# pylint: disable=invalid-name
@dataclass(init=False)
class BookData(ActivityObject):
    """shared fields for all book data and authors"""

    openlibraryKey: Optional[str] = None
    inventaireId: Optional[str] = None
    finnaKey: Optional[str] = None
    librarythingKey: Optional[str] = None
    goodreadsKey: Optional[str] = None
    bnfId: Optional[str] = None
    viaf: Optional[str] = None
    wikidata: Optional[str] = None
    asin: Optional[str] = None
    aasin: Optional[str] = None
    isfdb: Optional[str] = None
    lastEditedBy: Optional[str] = None


# pylint: disable=invalid-name
@dataclass(init=False)
class Book(BookData):
    """serializes an edition or work, abstract"""

    title: str
    sortTitle: str = None
    subtitle: str = None
    description: str = ""
    languages: list[str] = field(default_factory=list)
    series: str = ""  # legacy, now deprecated
    seriesNumber: str = ""  # legacy, now deprecated
    seriesBooks: list[str] = field(default_factory=list)
    seriesIds: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    subjectPlaces: list[str] = field(default_factory=list)

    authors: list[str] = field(default_factory=list)
    firstPublishedDate: str = ""
    publishedDate: str = ""

    fileLinks: list[str] = field(default_factory=list)

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
    publishers: list[str] = field(default_factory=list)
    editionRank: int = 0

    type: str = "Edition"


@dataclass(init=False)
class Work(Book):
    """work instance of a book object"""

    lccn: str = ""
    editions: list[str] = field(default_factory=list)
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
    aliases: list[str] = field(default_factory=list)
    bio: str = ""
    wikipediaLink: str = ""
    type: str = "Author"
    website: str = ""


@dataclass(init=False)
class Series(OrderedCollection, BookData):
    """serializes a book series"""

    title: str = ""
    alternative_titles: list[str] = field(default_factory=list)
    type: str = "Series"


@dataclass(init=False)
class SeriesBook(CollectionItem):
    """a book in a series"""

    book: str
    series: str
    series_number: str = ""
    type: str = "SeriesBook"
