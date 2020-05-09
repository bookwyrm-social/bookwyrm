''' using another fedireads instance as a source of book data '''
import re
import requests

from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.db import transaction

from fedireads import models
from .abstract_connector import AbstractConnector, SearchResult, get_date
from .abstract_connector import match_from_mappings, update_from_mappings


class Connector(AbstractConnector):
    ''' interact with other instances '''
    def __init__(self, identifier):
        self.key_mappings = {
            'isbn_13': ('isbn_13', None),
            'isbn_10': ('isbn_10', None),
            'oclc_numbers': ('oclc_number', None),
            'lccn': ('lccn', None),
        }
        super().__init__(identifier)


    def format_search_result(self, search_result):
        return SearchResult(**search_result)


    def parse_search_data(self, data):
        return data


    def get_or_create_book(self, remote_id):
        ''' pull up a book record by whatever means possible '''
        # re-construct a remote id from the int and books_url
        if re.match(r'^\d+$', remote_id):
            remote_id = self.books_url + '/' + remote_id
        book = models.Book.objects.select_subclasses().filter(
            remote_id=remote_id
        ).first()
        if book:
            if isinstance(book, models.Work):
                return book.default_edition
            return book

        # no book was found, so we start creating a new one
        response = requests.get(
            remote_id,
            headers={
                'Accept': 'application/activity+json; charset=utf-8',
            },
        )
        if not response.ok:
            response.raise_for_status()
        data = response.json()

        if data['book_type'] == 'work':
            work_data = data
            try:
                edition_data = data['editions'][0]
            except KeyError:
                # hack: re-use the work data as the edition data
                edition_data = data
        else:
            edition_data = data
            try:
                work_data = data['work']
            except KeyError:
                # hack: re-use the work data as the edition data
                work_data = data

        with transaction.atomic():
            # create both work and a default edition
            work_key = edition_data.get('url')
            work = self.create_book(work_key, work_data, models.Work)

            ed_key = edition_data.get('url')
            edition = self.create_book(ed_key, edition_data, models.Edition)
            edition.default = True
            edition.parent_work = work
            edition.save()

        return edition


    def get_cover_from_data(self, data):
        return None


    def get_authors_from_data(self, data):
        authors = []

        for author_url in data.get('authors', []):
            authors.append(self.get_or_create_author(author_url))
        return authors


    def update_book(self, book, data=None):
        ''' add remote data to a local book '''
        if not data:
            response = requests.get(
                book.remote_id,
                headers={
                    'Accept': 'application/activity+json; charset=utf-8',
                },
            )
            if not response.ok:
                response.raise_for_status()

            data = response.json()

        match = match_from_mappings(data, {})
        if match:
            return match

        # great, we can update our book.
        mappings = {
            'published_date': ('published_date', get_date),
            'first_published_date': ('first_published_date', get_date),
        }
        book = update_from_mappings(book, data, mappings)

        if not book.remote_id:
            book.remote_id = response.url
        if not book.connector:
            book.connector = self.connector
        book.save()

        if data.get('parent_work'):
            work = self.get_or_create_book(data.get('parent_work'))
            book.parent_work = work

        for author_blob in data.get('authors', []):
            author_blob = author_blob.get('author', author_blob)
            author_id = author_blob['key']
            author_id = author_id.split('/')[-1]
            book.authors.add(self.get_or_create_author(author_id))

        if book.sync_cover and data.get('covers') and data['covers']:
            book.cover.save(*get_cover(data['covers'][0]), save=True)

        return book


    def get_or_create_author(self, remote_id):
        ''' load that author '''
        try:
            return models.Author.objects.get(remote_id=remote_id)
        except ObjectDoesNotExist:
            pass

        resp = requests.get(
            remote_id,
            headers={
                'Accept': 'application/activity+json; charset=utf-8',
            },
        )
        if not resp.ok:
            resp.raise_for_status()

        data = resp.json()

        # ingest a new author
        author = models.Author(remote_id=remote_id)
        mappings = {
            'born': ('born', get_date),
            'died': ('died', get_date),
        }
        author = update_from_mappings(author, data, mappings)
        author.save()

        return author


    def expand_book_data(self, book):
        pass


def get_cover(cover_url):
    ''' ask openlibrary for the cover '''
    image_name = cover_url.split('/')[-1]
    response = requests.get(cover_url)
    if not response.ok:
        response.raise_for_status()
    image_content = ContentFile(response.content)
    return [image_name, image_content]
