''' openlibrary data connector '''
import re

from bookwyrm import models
from .abstract_connector import AbstractConnector, SearchResult, Mapping
from .abstract_connector import ConnectorException, get_data
from .openlibrary_languages import languages


class Connector(AbstractConnector):
    ''' instantiate a connector for OL '''
    def __init__(self, identifier):
        super().__init__(identifier)

        get_first = lambda a: a[0]
        get_remote_id = lambda a: self.base_url + a
        self.book_mappings = [
            Mapping('title'),
            Mapping('id', remote_field='key', formatter=get_remote_id),
            Mapping(
                'cover', remote_field='covers', formatter=self.get_cover_url),
            Mapping('sortTitle', remote_field='sort_title'),
            Mapping('subtitle'),
            Mapping('description', formatter=get_description),
            Mapping('languages', formatter=get_languages),
            Mapping('series', formatter=get_first),
            Mapping('seriesNumber', remote_field='series_number'),
            Mapping('subjects'),
            Mapping('subjectPlaces'),
            Mapping('isbn13', formatter=get_first),
            Mapping('isbn10', formatter=get_first),
            Mapping('lccn', formatter=get_first),
            Mapping(
                'oclcNumber', remote_field='oclc_numbers',
                formatter=get_first
            ),
            Mapping(
                'openlibraryKey', remote_field='key',
                formatter=get_openlibrary_key
            ),
            Mapping('goodreadsKey', remote_field='goodreads_key'),
            Mapping('asin'),
            Mapping(
                'firstPublishedDate', remote_field='first_publish_date',
            ),
            Mapping('publishedDate', remote_field='publish_date'),
            Mapping('pages', remote_field='number_of_pages'),
            Mapping('physicalFormat', remote_field='physical_format'),
            Mapping('publishers'),
        ]

        self.author_mappings = [
            Mapping('id', remote_field='key', formatter=get_remote_id),
            Mapping('name'),
            Mapping(
                'openlibraryKey', remote_field='key',
                formatter=get_openlibrary_key
            ),
            Mapping('born', remote_field='birth_date'),
            Mapping('died', remote_field='death_date'),
            Mapping('bio', formatter=get_description),
        ]


    def get_remote_id_from_data(self, data):
        ''' format a url from an openlibrary id field '''
        try:
            key = data['key']
        except KeyError:
            raise ConnectorException('Invalid book data')
        return '%s/%s' % (self.books_url, key)


    def is_work_data(self, data):
        return bool(re.match(r'^[\/\w]+OL\d+W$', data['key']))


    def get_edition_from_work_data(self, data):
        try:
            key = data['key']
        except KeyError:
            raise ConnectorException('Invalid book data')
        url = '%s/%s/editions' % (self.books_url, key)
        data = get_data(url)
        return pick_default_edition(data['entries'])


    def get_work_from_edition_date(self, data):
        try:
            key = data['works'][0]['key']
        except (IndexError, KeyError):
            raise ConnectorException('No work found for edition')
        url = '%s/%s' % (self.books_url, key)
        return get_data(url)


    def get_authors_from_data(self, data):
        ''' parse author json and load or create authors '''
        for author_blob in data.get('authors', []):
            author_blob = author_blob.get('author', author_blob)
            # this id is "/authors/OL1234567A"
            author_id = author_blob['key']
            url = '%s/%s.json' % (self.base_url, author_id)
            yield self.get_or_create_author(url)


    def get_cover_url(self, cover_blob):
        ''' ask openlibrary for the cover '''
        cover_id = cover_blob[0]
        image_name = '%s-M.jpg' % cover_id
        return '%s/b/id/%s' % (self.covers_url, image_name)


    def parse_search_data(self, data):
        return data.get('docs')


    def format_search_result(self, search_result):
        # build the remote id from the openlibrary key
        key = self.books_url + search_result['key']
        author = search_result.get('author_name') or ['Unknown']
        return SearchResult(
            title=search_result.get('title'),
            key=key,
            author=', '.join(author),
            year=search_result.get('first_publish_year'),
        )


    def load_edition_data(self, olkey):
        ''' query openlibrary for editions of a work '''
        url = '%s/works/%s/editions.json' % (self.books_url, olkey)
        return get_data(url)


    def expand_book_data(self, book):
        work = book
        # go from the edition to the work, if necessary
        if isinstance(book, models.Edition):
            work = book.parent_work

        # we can mass download edition data from OL to avoid repeatedly querying
        edition_options = self.load_edition_data(work.openlibrary_key)
        for edition_data in edition_options.get('entries'):
            self.create_edition_from_data(work, edition_data)


def get_description(description_blob):
    ''' descriptions can be a string or a dict '''
    if isinstance(description_blob, dict):
        return description_blob.get('value')
    return  description_blob


def get_openlibrary_key(key):
    ''' convert /books/OL27320736M into OL27320736M '''
    return key.split('/')[-1]


def get_languages(language_blob):
    ''' /language/eng -> English '''
    langs = []
    for lang in language_blob:
        langs.append(
            languages.get(lang.get('key', ''), None)
        )
    return langs


def pick_default_edition(options):
    ''' favor physical copies with covers in english '''
    if not options:
        return None
    if len(options) == 1:
        return options[0]

    options = [e for e in options if e.get('cover')] or options
    options = [e for e in options if \
        '/languages/eng' in str(e.get('languages'))] or options
    formats = ['paperback', 'hardcover', 'mass market paperback']
    options = [e for e in options if \
        str(e.get('physical_format')).lower() in formats] or options
    options = [e for e in options if e.get('isbn_13')] or options
    options = [e for e in options if e.get('ocaid')] or options
    return options[0]
