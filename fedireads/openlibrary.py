''' activitystream api and books '''
from django.core.exceptions import ObjectDoesNotExist
from fedireads.models import Author, Book, Work
from fedireads.settings import OL_URL
import requests

def get_or_create_book(olkey, user=None, update=True):
    ''' add a book '''
    # check if this is a valid open library key, and a book
    olkey = olkey
    response = requests.get(OL_URL + olkey + '.json')
    if not response.ok:
        response.raise_for_status()

    # get the existing entry from our db, if it exists
    try:
        book = Book.objects.get(openlibrary_key=olkey)
        if not update:
            return book
    except ObjectDoesNotExist:
        book = Book(openlibrary_key=olkey)
    data = response.json()
    book.data = data
    if user and user.is_authenticated:
        book.added_by = user
    book.save()
    for work_id in data['works']:
        work_id = work_id['key']
        book.works.add(get_or_create_work(work_id))
    for author_id in data['authors']:
        author_id = author_id['key']
        book.authors.add(get_or_create_author(author_id))
    return book

def get_or_create_work(olkey):
    ''' load em up '''
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
    try:
        author = Author.objects.get(openlibrary_key=olkey)
    except ObjectDoesNotExist:
        response = requests.get(OL_URL + olkey + '.json')
        data = response.json()
        author = Author(openlibrary_key=olkey, data=data)
        author.save()
    return author

