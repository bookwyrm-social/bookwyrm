''' openlibrary data connector '''
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
import re
import requests

from fedireads import models
from .abstract_connector import AbstractConnector, SearchResult


class OpenLibraryConnector(AbstractConnector):
    ''' instantiate a connector for OL '''
    def __init__(self):
        super().__init__('openlibrary')


    def search(self, query):
        ''' query openlibrary search '''
        resp = requests.get('%s/search.json' % self.url, params={'q': query})
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
            ))
        return results


    def get_or_create_book(self, olkey):
        ''' pull up a book record by whatever means possible '''
        if re.match(r'^OL\d+W$', olkey):
            model = models.Work
        elif re.match(r'^OL\d+M$', olkey):
            model = models.Edition
        else:
            raise ValueError('Invalid OpenLibrary ID')

        try:
            book = model.objects.get(openlibrary_key=olkey)
            return book
        except ObjectDoesNotExist:
            # no book was found, so we start creating a new one
            book = model(openlibrary_key=olkey)

        # load the book json from openlibrary.org
        response = requests.get('%s/works/%s.json' % (self.url, olkey))
        if not response.ok:
            response.raise_for_status()

        data = response.json()

        # great, we can update our book.
        book.title = data['title']
        description = data.get('description')
        if description:
            if isinstance(description, dict):
                description = description.get('value')
            book.description = description
        book.pages = data.get('pages')
        #book.published_date = data.get('publish_date')

        book.save()

        # this book sure as heck better be an edition
        if data.get('works'):
            key = data.get('works')[0]['key']
            key = key.split('/')[-1]
            work = self.get_or_create_book(key)
            book.parent_work = work

        # we also need to know the author get the cover
        for author_blob in data.get('authors', []):
            # this id is "/authors/OL1234567A" and we want just "OL1234567A"
            author_blob = author_blob.get('author', author_blob)
            author_id = author_blob['key']
            author_id = author_id.split('/')[-1]
            book.authors.add(self.get_or_create_author(author_id))

        if data.get('covers') and len(data['covers']):
            book.cover.save(*self.get_cover(data['covers'][0]), save=True)

        return book


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
        bio = data.get('bio')
        if bio:
            if isinstance(bio, dict):
                bio = bio.get('value')
            author.bio = bio
        name = data['name']
        author.name = name
        # TODO this is making some BOLD assumption
        author.last_name = name.split(' ')[-1]
        author.first_name = ' '.join(name.split(' ')[:-1])
        #author.born = data.get('birth_date')
        #author.died = data.get('death_date')
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


    def update_book(self, book_obj):
        pass
