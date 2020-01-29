''' activitystream api and books '''
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
import requests

from fedireads.models import Author, Book, Work
from fedireads.settings import OL_URL


def get_or_create_book(olkey, user=None, update=False):
    ''' add a book '''
    # TODO: check if this is a valid open library key, and a book
    olkey = olkey

    # get the existing entry from our db, if it exists
    try:
        book = Book.objects.get(openlibrary_key=olkey)
        if not update:
            return book
        # we have the book, but still want to update it from OL
    except ObjectDoesNotExist:
        # no book was found, so we start creating a new one
        book = Book(openlibrary_key=olkey)

    # load the book json from openlibrary.org
    response = requests.get(OL_URL + olkey + '.json')
    if not response.ok:
        response.raise_for_status()

    data = response.json()
    book.data = data

    if user and user.is_authenticated:
        book.added_by = user

    # great, we can update our book.
    book.save()

    # we also need to know the author and works related to this book.
    for work_id in data['works']:
        work_id = work_id['key']
        book.works.add(get_or_create_work(work_id))

    for author_id in data['authors']:
        author_id = author_id['key']
        book.authors.add(get_or_create_author(author_id))

    if len(data['covers']):
        book.cover.save(*get_cover(data['covers'][0]), save=True)

    return book


def get_cover(cover_id):
    ''' ask openlibrary for the cover '''
    image_name = '%s-M.jpg' % cover_id
    url = 'https://covers.openlibrary.org/b/id/%s' % image_name
    response = requests.get(url)
    if not response.ok:
        response.raise_for_status()
    image_content = ContentFile(requests.get(url).content)
    return [image_name, image_content]


def get_or_create_work(olkey):
    ''' load em up '''
    # TODO: validate that this is a work key
    # TODO: error handling
    try:
        work = Work.objects.get(openlibrary_key=olkey)
    except ObjectDoesNotExist:
        response = requests.get(OL_URL + olkey + '.json')
        data = response.json()
        work = Work(openlibrary_key=olkey, data=data)
        work.save()
    return work


def get_or_create_author(olkey):
    ''' load that author '''
    # TODO: validate that this is an author key
    # TODO: error handling
    try:
        author = Author.objects.get(openlibrary_key=olkey)
    except ObjectDoesNotExist:
        response = requests.get(OL_URL + olkey + '.json')
        data = response.json()
        author = Author(openlibrary_key=olkey, data=data)
        author.save()
    return author

