''' openlibrary data connector '''
import re
import requests

from django.core.files.base import ContentFile
from django.db import transaction

from fedireads import models
from .abstract_connector import AbstractConnector, SearchResult
from .abstract_connector import update_from_mappings, get_date
from .openlibrary_languages import languages


class Connector(AbstractConnector):
    ''' instantiate a connector for OL '''
    def __init__(self, identifier):
        get_first = lambda a: a[0]
        self.book_mappings = {
            'publish_date': ('published_date', get_date),
            'first_publish_date': ('first_published_date', get_date),
            'description': ('description', get_description),
            'isbn_13': ('isbn_13', get_first),
            'oclc_numbers': ('oclc_number', get_first),
            'lccn': ('lccn', get_first),
            'languages': ('languages', get_languages),
            'number_of_pages': ('pages', None),
            'series': ('series', get_first),
        }
        super().__init__(identifier)


    def search(self, query):
        ''' query openlibrary search '''
        resp = requests.get(
            '%s%s' % (self.search_url, query),
            headers={
                'Accept': 'application/json; charset=utf-8',
            },
        )
        if not resp.ok:
            resp.raise_for_status()
        data = resp.json()
        results = []

        for doc in data['docs'][:5]:
            key = doc['key']
            key = key.split('/')[-1]
            author = doc.get('author_name') or ['Unknown']
            results.append(SearchResult(
                doc.get('title'),
                key,
                author[0],
                doc.get('first_publish_year'),
                doc
            ))
        return results


    def get_or_create_book(self, olkey):
        ''' pull up a book record by whatever means possible.
        if you give a work key, it should give you the default edition,
        annotated with work data. '''

        book = models.Book.objects.select_subclasses().filter(
            openlibrary_key=olkey
        ).first()
        if book:
            if isinstance(book, models.Work):
                return book.default_edition
            return book

        # no book was found, so we start creating a new one
        if re.match(r'^OL\d+W$', olkey):
            with transaction.atomic():
                # create both work and a default edition
                work_data = self.load_book_data(olkey)
                work = self.create_book(olkey, work_data, models.Work)

                edition_options = self.load_edition_data(olkey).get('entries')
                edition_data = pick_default_edition(edition_options)
                key = edition_data.get('key').split('/')[-1]
                edition = self.create_book(key, edition_data, models.Edition)
                edition.parent_work = work
                edition.save()
        else:
            with transaction.atomic():
                edition_data = self.load_book_data(olkey)
                edition = self.create_book(olkey, edition_data, models.Edition)

                work_key = edition_data.get('works')[0]['key'].split('/')[-1]
                work = models.Work.objects.filter(
                    openlibrary_key=work_key
                ).first()
                if not work:
                    work_data = self.load_book_data(work_key)
                    work = self.create_book(work_key, work_data, models.Work)
                edition.parent_work = work
                edition.save()
        if not edition.authors and work.authors:
            edition.authors.set(work.authors.all())
            edition.author_text = ', '.join(a.name for a in edition.authors)

        return edition


    def create_book(self, key, data, model):
        ''' create a work or edition from data '''
        book = model.objects.create(
            openlibrary_key=key,
            title=data['title'],
            connector=self.connector,
        )
        return self.update_book_from_data(book, data)


    def update_book_from_data(self, book, data):
        ''' updaet a book model instance from ol data '''
        # populate the simple data fields
        update_from_mappings(book, data, self.book_mappings)
        book.save()

        authors = self.get_authors_from_data(data)
        for author in authors:
            book.authors.add(author)
        if authors:
            book.author_text = ', '.join(a.name for a in authors)

        if data.get('covers'):
            book.cover.save(*self.get_cover(data['covers'][0]), save=True)
        return book


    def update_book(self, book):
        ''' load new data '''
        if not book.sync and not book.sync_cover:
            return

        data = self.load_book_data(book.openlibrary_key)
        if book.sync_cover and data.get('covers'):
            book.cover.save(*self.get_cover(data['covers'][0]), save=True)
        if book.sync:
            book = self.update_book_from_data(book, data)
        return book


    def get_authors_from_data(self, data):
        ''' parse author json and load or create authors '''
        authors = []
        for author_blob in data.get('authors', []):
            # this id is "/authors/OL1234567A" and we want just "OL1234567A"
            author_blob = author_blob.get('author', author_blob)
            author_id = author_blob['key'].split('/')[-1]
            authors.append(self.get_or_create_author(author_id))
        return authors


    def load_book_data(self, olkey):
        ''' query openlibrary for data on a book '''
        response = requests.get('%s/works/%s.json' % (self.url, olkey))
        if not response.ok:
            response.raise_for_status()
        data = response.json()
        return data


    def load_edition_data(self, olkey):
        ''' query openlibrary for editions of a work '''
        response = requests.get(
            '%s/works/%s/editions.json' % (self.url, olkey))
        if not response.ok:
            response.raise_for_status()
        data = response.json()
        return data


    def expand_book_data(self, book):
        work = book
        if isinstance(book, models.Edition):
            work = book.parent_work

        edition_options = self.load_edition_data(work.openlibrary_key)
        for edition_data in edition_options.get('entries'):
            olkey = edition_data.get('key').split('/')[-1]
            if models.Edition.objects.filter(openlibrary_key=olkey).count():
                continue
            edition = self.create_book(olkey, edition_data, models.Edition)
            edition.parent_work = work
            edition.save()
            if not edition.authors and work.authors:
                edition.authors.set(work.authors.all())


    def get_or_create_author(self, olkey):
        ''' load that author '''
        if not re.match(r'^OL\d+A$', olkey):
            raise ValueError('Invalid OpenLibrary author ID')
        try:
            return models.Author.objects.get(openlibrary_key=olkey)
        except models.Author.DoesNotExist:
            pass

        response = requests.get('%s/authors/%s.json' % (self.url, olkey))
        if not response.ok:
            response.raise_for_status()

        data = response.json()
        author = models.Author(openlibrary_key=olkey)
        mappings = {
            'birth_date': ('born', get_date),
            'death_date': ('died', get_date),
            'bio': ('bio', get_description),
        }
        author = update_from_mappings(author, data, mappings)
        # TODO this is making some BOLD assumption
        name = data.get('name')
        if name:
            author.last_name = name.split(' ')[-1]
            author.first_name = ' '.join(name.split(' ')[:-1])
        author.save()

        return author


    def get_cover(self, cover_id):
        ''' ask openlibrary for the cover '''
        # TODO: get medium and small versions
        image_name = '%s-M.jpg' % cover_id
        url = '%s/b/id/%s' % (self.covers_url, image_name)
        response = requests.get(url)
        if not response.ok:
            response.raise_for_status()
        image_content = ContentFile(response.content)
        return [image_name, image_content]


def get_description(description_blob):
    ''' descriptions can be a string or a dict '''
    if isinstance(description_blob, dict):
        return description_blob.get('value')
    return  description_blob


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
