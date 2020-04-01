''' openlibrary data connector '''
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
import re
import requests

from fedireads import models
from .abstract_connector import AbstractConnector, SearchResult
from .abstract_connector import update_from_mappings, get_date
from .openlibrary_languages import languages


class Connector(AbstractConnector):
    ''' instantiate a connector for OL '''
    def __init__(self, identifier):
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

        try:
            book = models.Book.objects.select_subclasses().get(
                openlibrary_key=olkey
            )
            return book
        except ObjectDoesNotExist:
            pass
        # no book was found, so we start creating a new one
        model = models.Edition
        if re.match(r'^OL\d+W$', olkey):
            model = models.Work
        book = model(openlibrary_key=olkey)
        return self.update_book(book)


    def update_book(self, book):
        ''' query openlibrary for data on a book '''
        olkey = book.openlibrary_key
        # load the book json from openlibrary.org
        response = requests.get('%s/works/%s.json' % (self.url, olkey))
        if not response.ok:
            response.raise_for_status()
        data = response.json()
        if not book.source_url:
            book.source_url = response.url
        return self.update_from_data(book, data)


    def update_from_data(self, book, data, work=None):
        ''' update a book from a json blob '''
        mappings = {
            'publish_date': ('published_date', get_date),
            'first_publish_date': ('first_published_date', get_date),
            'description': ('description', get_description),
            'isbn_13': ('isbn', None),
            'oclc_numbers': ('oclc_number', lambda a: a[0]),
            'lccn': ('lccn', lambda a: a[0]),
            'languages': ('languages', get_languages),
        }
        book = update_from_mappings(book, data, mappings)

        if 'identifiers' in data:
            if 'goodreads' in data['identifiers']:
                book.goodreads_key = data['identifiers']['goodreads']

        if not book.connector:
            book.connector = self.connector
        book.save()

        # this book sure as heck better be an edition
        if not work:
            work = None
            if data.get('works'):
                key = data.get('works')[0]['key']
                key = key.split('/')[-1]
                work = self.get_or_create_book(key)
        book.parent_work = work

        if isinstance(book, models.Work):
            # load editions of a work
            self.get_editions_of_work(book)

        # we also need to know the author get the cover
        for author_blob in data.get('authors', []):
            # this id is "/authors/OL1234567A" and we want just "OL1234567A"
            author_blob = author_blob.get('author', author_blob)
            author_id = author_blob['key']
            author_id = author_id.split('/')[-1]
            book.authors.add(self.get_or_create_author(author_id))

        if book.sync_cover and data.get('covers') and len(data['covers']):
            book.cover.save(*self.get_cover(data['covers'][0]), save=True)

        return book


    def get_editions_of_work(self, work):
        ''' get all editions of a work '''
        response = requests.get(
            '%s/works/%s/editions.json' % (self.url, work.openlibrary_key))
        edition_data = response.json()
        for data in edition_data.get('entries', []):
            try:
                olkey = data['key'].split('/')[-1]
            except KeyError:
                # bad data I guess?
                continue

            try:
                models.Edition.objects.get(openlibrary_key=olkey)
                continue
            except ObjectDoesNotExist:
                book = models.Edition.objects.create(openlibrary_key=olkey)
                self.update_from_data(book, data, work=work)
        set_default_edition(work)


    def get_or_create_author(self, olkey):
        ''' load that author '''
        if not re.match(r'^OL\d+A$', olkey):
            raise ValueError('Invalid OpenLibrary author ID')
        try:
            return models.Author.objects.get(openlibrary_key=olkey)
        except ObjectDoesNotExist:
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


def set_default_edition(work):
    ''' pick one edition to be what gets shown by default '''
    # check for an existing default work, in which case we're done
    if models.Edition.objects.filter(
            parent_work=work,
            default=True
        ).count():
        return
    editions = models.Edition.objects.filter(
        parent_work=work,
    ).all()
    options = [e for e in editions if 'English' in e.languages] or editions
    options = [e for e in options if e.cover] or options
    options = sorted(
        options,
        key=lambda e: e.published_date.year if e.published_date else None
    )
    if len(options):
        options[0].default = True
        options[0].save()


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


