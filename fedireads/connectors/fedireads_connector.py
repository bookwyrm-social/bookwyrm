''' using another fedireads instance as a source of book data '''
from uuid import uuid4

from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
import requests

from fedireads import models
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
            Mapping('born', remote_field='birth_date', formatter=get_date),
            Mapping('died', remote_field='death_date', formatter=get_date),
            Mapping('bio'),
        ]


    def is_work_data(self, data):
        return data['book_type'] == 'Work'


    def get_edition_from_work_data(self, data):
        return data['editions'][0]


    def get_work_from_edition_date(self, data):
        return data['work']


    def get_authors_from_data(self, data):
        for author_url in data.get('authors', []):
            yield self.get_or_create_author(author_url)


    def get_cover_from_data(self, data):
        cover_data = data.get('attachment')
        if not cover_data:
            return None
        cover_url = cover_data[0].get('url')
        response = requests.get(cover_url)
        if not response.ok:
            response.raise_for_status()

        image_name = str(uuid4()) + cover_url.split('.')[-1]
        image_content = ContentFile(response.content)
        return [image_name, image_content]


    def get_or_create_author(self, remote_id):
        ''' load that author '''
        try:
            return models.Author.objects.get(remote_id=remote_id)
        except ObjectDoesNotExist:
            pass

        data = get_data(remote_id)

        # ingest a new author
        author = models.Author(remote_id=remote_id)
        author = update_from_mappings(author, data, self.author_mappings)
        author.save()

        return author


    def parse_search_data(self, data):
        return data


    def format_search_result(self, search_result):
        return SearchResult(**search_result)


    def expand_book_data(self, book):
        # TODO
        pass
