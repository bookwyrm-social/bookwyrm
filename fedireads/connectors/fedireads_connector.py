''' using another fedireads instance as a source of book data '''
from uuid import uuid4

from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
import requests

from fedireads import models
from .abstract_connector import AbstractConnector, SearchResult
from .abstract_connector import update_from_mappings, get_date, get_data


class Connector(AbstractConnector):
    ''' interact with other instances '''
    def __init__(self, identifier):
        super().__init__(identifier)
        self.book_mappings = self.key_mappings.copy()
        self.book_mappings.update({
            'published_date': ('published_date', get_date),
            'first_published_date': ('first_published_date', get_date),
        })


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
        mappings = {
            'born': ('born', get_date),
            'died': ('died', get_date),
        }
        author = update_from_mappings(author, data, mappings)
        author.save()

        return author


    def parse_search_data(self, data):
        return data


    def format_search_result(self, search_result):
        return SearchResult(**search_result)


    def expand_book_data(self, book):
        # TODO
        pass
