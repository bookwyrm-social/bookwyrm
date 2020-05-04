''' using another fedireads instance as a source of book data '''
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
import requests

from fedireads import models
from .abstract_connector import AbstractConnector
from .abstract_connector import update_from_mappings, get_date


class Connector(AbstractConnector):
    ''' interact with other instances '''

    def search(self, query):
        ''' right now you can't search fedireads, but... '''
        resp = requests.get(
            '%s%s' % (self.search_url, query),
            headers={
                'Accept': 'application/activity+json; charset=utf-8',
            },
        )
        if not resp.ok:
            resp.raise_for_status()

        return resp.json()


    def get_or_create_book(self, remote_id):
        ''' pull up a book record by whatever means possible '''
        try:
            book = models.Book.objects.select_subclasses().get(
                remote_id=remote_id
            )
            return book
        except ObjectDoesNotExist:
            if self.model.is_self:
                # we can't load a book from a remote server, this is it
                return None
            # no book was found, so we start creating a new one
            book = models.Book(remote_id=remote_id)


    def update_book(self, book):
        ''' add remote data to a local book '''
        remote_id = book.remote_id
        response = requests.get(
            '%s/%s' % (self.base_url, remote_id),
            headers={
                'Accept': 'application/activity+json; charset=utf-8',
            },
        )
        if not response.ok:
            response.raise_for_status()

        data = response.json()

        # great, we can update our book.
        mappings = {
            'published_date': ('published_date', get_date),
            'first_published_date': ('first_published_date', get_date),
        }
        book = update_from_mappings(book, data, mappings)

        if not book.source_url:
            book.source_url = response.url
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

        resp = requests.get('%s/authors/%s.json' % (self.url, remote_id))
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


def get_cover(cover_url):
    ''' ask openlibrary for the cover '''
    image_name = cover_url.split('/')[-1]
    response = requests.get(cover_url)
    if not response.ok:
        response.raise_for_status()
    image_content = ContentFile(response.content)
    return [image_name, image_content]
