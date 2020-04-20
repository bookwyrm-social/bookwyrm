''' handle reading a csv from goodreads '''
import re
import csv
import dateutil.parser
from requests import HTTPError

from fedireads import books_manager
from fedireads import outgoing
from fedireads.models import Edition, ReadThrough, User
from fedireads.tasks import app


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


def async_import(user, csv_file):
    entries = list(csv.DictReader(csv_file))[:MAX_ENTRIES]
    return import_data.delay(user.id, entries)

@app.task
def import_data(user_id, entries):
    user = User.objects.get(pk=user_id)
    results = []
    reviews = []
    failures = []
    for item in entries:
        item = GoodreadsItem(item)
        try:
            item.resolve()
        except HTTPError:
            pass
        if item.book:
            results.append(item)
            if item.rating or item.review:
                reviews.append(item)
        else:
            failures.append(item)

    outgoing.handle_import_books(user, results)
    for item in reviews:
        review_title = "Review of {!r} on Goodreads".format(
            item.book.title,
        ) if item.review else ""
        outgoing.handle_review(
            user,
            item.book,
            review_title,
            item.review,
            item.rating,
        )


class GoodreadsItem:
    ''' a processed line in a goodreads csv '''
    def __init__(self, line):
        self.line = line
        self.book = None

    def resolve(self):
        ''' try various ways to lookup a book '''
        self.book = (
            self.get_book_from_db_isbn() or
            self.get_book_from_isbn() or
            self.get_book_from_title_author()
        )

    def get_book_from_db_isbn(self):
        ''' see if we already know about the book '''
        try:
            return Edition.objects.get(isbn=self.isbn)
        except Edition.DoesNotExist:
            return None

    def get_book_from_isbn(self):
        ''' search by isbn '''
        search_results = books_manager.search(self.isbn)
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
    def isbn(self):
        return unquote_string(self.line['ISBN13'])

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

    @property
    def date_added(self):
        if self.line['Date Added']:
            return dateutil.parser.parse(self.line['Date Added'])

    @property
    def date_read(self):
        if self.line['Date Read']:
            return dateutil.parser.parse(self.line['Date Read'])

    @property
    def reads(self):
        return [ReadThrough(
            # Date added isn't the start date, but it's (perhaps) better than nothing.
            start_date=self.date_added,
            finish_date=self.date_read,
            pages_read=None,
        )]

    def __repr__(self):
        return "<GoodreadsItem {!r}>".format(self.line['Title'])

    def __str__(self):
        return "{} by {}".format(self.line['Title'], self.line['Author'])
