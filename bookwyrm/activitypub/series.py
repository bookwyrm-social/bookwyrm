"""book series"""

from dataclasses import dataclass, field

from .ordered_collection import OrderedCollection, CollectionItem
from .book import BookData


@dataclass(init=False)
class Series(BookData, OrderedCollection):
    """serializes a book series"""

    actor: str
    name: str
    alternativeNames: list[str] = field(default_factory=list)
    type: str = "Series"


@dataclass(init=False)
class SeriesBook(CollectionItem):
    """a book in a series"""

    actor: str
    book: str
    series: str
    seriesNumber: int = None
    type: str = "SeriesBook"
