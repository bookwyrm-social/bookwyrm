''' using another bookwyrm instance as a source of book data '''
from uuid import uuid4

from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.db import transaction
import requests

from bookwyrm import models
from .abstract_connector import AbstractConnector, SearchResult, Mapping
from .abstract_connector import update_from_mappings, get_date, get_data


class Connector(AbstractConnector):
    ''' interact with other instances '''
    def __init__(self, identifier):
        super().__init__(identifier)
        self.key_mappings = [
            Mapping('isbn_13', model=models.Edition),
            Mapping('isbn_10', model=models.Edition),
            Mapping('lccn', model=models.Work),
            Mapping('oclc_number', model=models.Edition),
            Mapping('openlibrary_key'),
            Mapping('goodreads_key'),
            Mapping('asin'),
        ]

        self.book_mappings = self.key_mappings + [
            Mapping('sort_title'),
            Mapping('subtitle'),
            Mapping('description'),
            Mapping('languages'),
            Mapping('series'),
            Mapping('series_number'),
            Mapping('subjects'),
            Mapping('subject_places'),
            Mapping('first_published_date'),
            Mapping('published_date'),
            Mapping('pages'),
            Mapping('physical_format'),
            Mapping('publishers'),
        ]

        self.author_mappings = [
            Mapping('name'),
            Mapping('bio'),
            Mapping('openlibrary_key'),
            Mapping('wikipedia_link'),
            Mapping('aliases'),
            Mapping('born', formatter=get_date),
            Mapping('died', formatter=get_date),
        ]


    def get_remote_id_from_data(self, data):
        return data.get('id')


    def is_work_data(self, data):
        return data['type'] == 'Work'


    def get_edition_from_work_data(self, data):
        ''' we're served a list of edition urls '''
        path = data['editions'][0]
        return get_data(path)


    def get_work_from_edition_date(self, data):
        return get_data(data['work'])


    def get_authors_from_data(self, data):
        for author_url in data.get('authors', []):
            yield self.get_or_create_author(author_url)


    def get_cover_from_data(self, data):
        cover_data = data.get('attachment')
        if not cover_data:
            return None
        try:
            cover_url = cover_data[0].get('url')
        except IndexError:
            return None
        try:
            response = requests.get(cover_url)
        except ConnectionError:
            return None

        if not response.ok:
            return None

        image_name = str(uuid4()) + '.' + cover_url.split('.')[-1]
        image_content = ContentFile(response.content)
        return [image_name, image_content]


    def get_or_create_author(self, remote_id):
        ''' load that author '''
        try:
            return models.Author.objects.get(origin_id=remote_id)
        except ObjectDoesNotExist:
            pass

        data = get_data(remote_id)

        # ingest a new author
        author = models.Author(origin_id=remote_id)
        author = update_from_mappings(author, data, self.author_mappings)
        author.save()

        return author


    def parse_search_data(self, data):
        return data


    def format_search_result(self, search_result):
        return SearchResult(**search_result)


    def expand_book_data(self, book):
        work = book
        # go from the edition to the work, if necessary
        if isinstance(book, models.Edition):
            work = book.parent_work

        # it may be that we actually want to request this url
        editions_url = '%s/editions?page=true' % work.remote_id
        edition_options = get_data(editions_url)
        for edition_data in edition_options['orderedItems']:
            with transaction.atomic():
                edition = self.create_book(
                    edition_data['id'],
                    edition_data,
                    models.Edition
                )
                edition.parent_work = work
                edition.save()
            if not edition.authors.exists() and work.authors.exists():
                edition.authors.set(work.authors.all())
