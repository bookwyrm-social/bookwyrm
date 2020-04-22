import re
import dateutil.parser

from django.db import models
from django.utils import timezone

from fedireads import books_manager
from fedireads.models import Edition, ReadThrough, User, Book
from fedireads.utils.fields import JSONField

# Mapping goodreads -> fedireads shelf titles.
GOODREADS_SHELVES = {
    'read': 'read',
    'currently-reading': 'reading',
    'to-read': 'to-read',
}

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

class ImportJob(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_date = models.DateTimeField(default=timezone.now)
    task_id = models.CharField(max_length=100, null=True)
    import_status = models.ForeignKey(
        'Status', null=True, on_delete=models.PROTECT)

class ImportItem(models.Model):
    job = models.ForeignKey(
        ImportJob,
        on_delete=models.CASCADE,
        related_name='items')
    index = models.IntegerField()
    data = JSONField()
    book = models.ForeignKey(
        Book, on_delete=models.SET_NULL, null=True, blank=True)
    fail_reason = models.TextField(null=True)

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
            self.data['Title'],
            self.data['Author']
        )
        search_results = books_manager.search(search_term)
        if search_results:
            return books_manager.get_or_create_book(search_results[0].key)

    @property
    def isbn(self):
        return unquote_string(self.data['ISBN13'])

    @property
    def shelf(self):
        ''' the goodreads shelf field '''
        if self.data['Exclusive Shelf']:
            return GOODREADS_SHELVES[self.data['Exclusive Shelf']]

    @property
    def review(self):
        return self.data['My Review']

    @property
    def rating(self):
        return int(self.data['My Rating'])

    @property
    def date_added(self):
        if self.data['Date Added']:
            return dateutil.parser.parse(self.data['Date Added'])

    @property
    def date_read(self):
        if self.data['Date Read']:
            return dateutil.parser.parse(self.data['Date Read'])

    @property
    def reads(self):
        return [ReadThrough(
            # date_added isn't the start date, but maybe better than nothing.
            start_date=self.date_added,
            finish_date=self.date_read,
            pages_read=None,
        )]

    def __repr__(self):
        return "<GoodreadsItem {!r}>".format(self.data['Title'])

    def __str__(self):
        return "{} by {}".format(self.data['Title'], self.data['Author'])
