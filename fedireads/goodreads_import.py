''' handle reading a csv from goodreads '''
import re
import csv
import itertools
from requests import HTTPError

from fedireads import books_manager


# Mapping goodreads -> fedireads shelf titles.
GOODREADS_SHELVES = {
    'read': 'read',
    'currently-reading': 'reading',
    'to-read': 'to-read',
}
# TODO: remove or notify about this in the UI
MAX_ENTRIES = 20


def unquote_string(text):
    ''' resolve csv quote weirdness '''
    match = re.match(r'="([^"]*)"', text)
    if match:
        return match.group(1)
    return text


def construct_search_term(title, author):
    ''' formulate a query for the data connector '''
    # Strip brackets (usually series title from search term)
    title = re.sub(r'\s*\([^)]*\)\s*', '', title)
    # Open library doesn't like including author initials in search term.
    author = re.sub(r'(\w\.)+\s*', '', author)

    return ' '.join([title, author])


class GoodreadsCsv:
    ''' define a goodreads csv '''
    def __init__(self, csv_file):
        self.reader = csv.DictReader(csv_file)

    def __iter__(self):
        for line in itertools.islice(self.reader, MAX_ENTRIES):
            entry = GoodreadsItem(line)
            try:
                entry.resolve()
            except HTTPError:
                pass
            yield entry


class GoodreadsItem:
    ''' a processed line in a goodreads csv '''
    def __init__(self, line):
        self.line = line
        self.book = None


    def resolve(self):
        ''' try various ways to lookup a book '''
        self.book = self.get_book_from_isbn()
        if not self.book:
            self.book = self.get_book_from_title_author()


    def get_book_from_isbn(self):
        ''' search by isbn '''
        isbn = unquote_string(self.line['ISBN13'])
        search_results = books_manager.search(isbn)
        if search_results:
            return books_manager.get_or_create_book(search_results[0].key)


    def get_book_from_title_author(self):
        ''' search by title and author '''
        search_term = construct_search_term(
            self.line['Title'],
            self.line['Author']
        )
        search_results = books_manager.search(search_term)
        if search_results:
            return books_manager.get_or_create_book(search_results[0].key)

    @property
    def shelf(self):
        ''' the goodreads shelf field '''
        if self.line['Exclusive Shelf']:
            return GOODREADS_SHELVES[self.line['Exclusive Shelf']]

    @property
    def review(self):
        return self.line['My Review']

    @property
    def rating(self):
        return int(self.line['My Rating'])

    def __repr__(self):
        return "<GoodreadsItem {!r}>".format(self.line['Title'])

    def __str__(self):
        return "{} by {}".format(self.line['Title'], self.line['Author'])
