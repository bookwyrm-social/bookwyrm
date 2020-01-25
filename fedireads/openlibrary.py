''' activitystream api and books '''
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.core.exceptions import ObjectDoesNotExist
from django.core import serializers
from fedireads.models import Book, Work
import requests

openlibrary_url = 'https://openlibrary.org'

def get_book(request, olkey):
    # check if this is a valid open library key, and a book
    response = requests.get(openlibrary_url + '/book/' + olkey + '.json')

    # get the existing entry from our db, if it exists
    try:
        book = Book.objects.get(openlibary_key=olkey)
    except ObjectDoesNotExist:
        book = Book(openlibary_key=olkey)
    data = response.json()
    book.data = data
    book.save()
    for work_id in data['works']:
        work_id = work_id['key']
        book.works.add(get_or_create_work(work_id))
    return HttpResponse(serializers.serialize('json', [book]))

def get_or_create_work(olkey):
    try:
        work = Work.objects.get(openlibary_key=olkey)
    except ObjectDoesNotExist:
        response = requests.get(openlibrary_url + '/work/' + olkey +'.json')
        data = response.json()
        work = Work(openlibary_key=olkey, data=data)
        work.save()
    return work

