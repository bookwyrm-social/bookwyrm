''' book and author data '''
from dataclasses import dataclass, field
from typing import List

from .base_activity import ActivityObject, Image

@dataclass(init=False)
class Book(ActivityObject):
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

    attachment: List[Image] = field(default=lambda: [])
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
    lccn: str
    editions: List[str]
    type: str = 'Work'



@dataclass(init=False)
class Author(ActivityObject):
    url: str
    name: str
    born: str
    died: str
    aliases: str
    bio: str
    openlibrary_key: str
    wikipedia_link: str
    type: str = 'Person'


def get_shelf(shelf, page=None):
    id_slug = shelf.remote_id
    if page:
        return get_shelf_page(shelf, page)
    count = shelf.books.count()
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': id_slug,
        'type': 'OrderedCollection',
        'totalItems': count,
        'first': '%s?page=1' % id_slug,
    }


def get_shelf_page(shelf, page):
    page = int(page)
    page_length = 10
    start = (page - 1) * page_length
    end = start + page_length
    shelf_page = shelf.books.all()[start:end]
    id_slug = shelf.local_id
    data = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': '%s?page=%d' % (id_slug, page),
        'type': 'OrderedCollectionPage',
        'totalItems': shelf.books.count(),
        'partOf': id_slug,
        'orderedItems': [get_book(b) for b in shelf_page],
    }
    if end <= shelf.books.count():
        # there are still more pages
        data['next'] = '%s?page=%d' % (id_slug, page + 1)
    if start > 0:
        data['prev'] = '%s?page=%d' % (id_slug, page - 1)
    return data
