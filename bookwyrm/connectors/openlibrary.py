''' openlibrary data connector '''
import re
import requests

from django.core.files.base import ContentFile

from bookwyrm import models
from .abstract_connector import AbstractConnector, SearchResult, Mapping
from .abstract_connector import ConnectorException
from .abstract_connector import get_date, get_data, update_from_mappings
from .openlibrary_languages import languages


class Connector(AbstractConnector):
    ''' instantiate a connector for OL '''
    def __init__(self, identifier):
        super().__init__(identifier)

        get_first = lambda a: a[0]
        self.key_mappings = [
            Mapping('isbn_13', model=models.Edition, formatter=get_first),
            Mapping('isbn_10', model=models.Edition, formatter=get_first),
            Mapping('lccn', model=models.Work, formatter=get_first),
            Mapping(
                'oclc_number',
                remote_field='oclc_numbers',
                model=models.Edition,
                formatter=get_first
            ),
            Mapping(
                'openlibrary_key',
                remote_field='key',
                formatter=get_openlibrary_key
            ),
            Mapping('goodreads_key'),
            Mapping('asin'),
        ]

        self.book_mappings = self.key_mappings + [
            Mapping('sort_title'),
            Mapping('subtitle'),
            Mapping('description', formatter=get_description),
            Mapping('languages', formatter=get_languages),
            Mapping('series', formatter=get_first),
            Mapping('series_number'),
            Mapping('subjects'),
            Mapping('subject_places'),
            Mapping(
                'first_published_date',
                remote_field='first_publish_date',
                formatter=get_date
            ),
            Mapping(
                'published_date',
                remote_field='publish_date',
                formatter=get_date
            ),
            Mapping(
                'pages',
                model=models.Edition,
                remote_field='number_of_pages'
            ),
            Mapping('physical_format', model=models.Edition),
            Mapping('publishers'),
        ]

        self.author_mappings = [
            Mapping('name'),
            Mapping('born', remote_field='birth_date', formatter=get_date),
            Mapping('died', remote_field='death_date', formatter=get_date),
            Mapping('bio', formatter=get_description),
        ]


    def get_remote_id_from_data(self, data):
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
            # this id is "/authors/OL1234567A" and we want just "OL1234567A"
            author_id = author_blob['key'].split('/')[-1]
            yield self.get_or_create_author(author_id)


    def get_cover_from_data(self, data):
        ''' ask openlibrary for the cover '''
        if not data.get('covers'):
            return None

        cover_id = data.get('covers')[0]
        image_name = '%s-M.jpg' % cover_id
        url = '%s/b/id/%s' % (self.covers_url, image_name)
        response = requests.get(url)
        if not response.ok:
            response.raise_for_status()
        image_content = ContentFile(response.content)
        return [image_name, image_content]


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
            olkey = edition_data.get('key').split('/')[-1]
            # make sure the edition isn't already in the database
            if models.Edition.objects.filter(openlibrary_key=olkey).count():
                continue

            # creates and populates the book from the data
            edition = self.create_book(olkey, edition_data, models.Edition)
            # ensures that the edition is associated with the work
            edition.parent_work = work
            edition.save()
            # get author data from the work if it's missing from the edition
            if not edition.authors and work.authors:
                edition.authors.set(work.authors.all())


    def get_or_create_author(self, olkey):
        ''' load that author '''
        if not re.match(r'^OL\d+A$', olkey):
            raise ValueError('Invalid OpenLibrary author ID')
        author = models.Author.objects.filter(openlibrary_key=olkey).first()
        if author:
            return author

        url = '%s/authors/%s.json' % (self.base_url, olkey)
        data = get_data(url)

        author = models.Author(openlibrary_key=olkey)
        author = update_from_mappings(author, data, self.author_mappings)
        author.save()

        return author


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
