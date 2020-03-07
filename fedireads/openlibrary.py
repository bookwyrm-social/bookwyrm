''' activitystream api and books '''
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
import re
import requests

from fedireads import models
from fedireads.settings import OL_URL


def book_search(query):
    ''' look up a book '''
    response = requests.get('%s/search.json' % OL_URL, params={'q': query})
    if not response.ok:
        response.raise_for_status()
    data = response.json()
    results = []

    for doc in data['docs'][:5]:
        key = doc['key']
        key = key.split('/')[-1]
        author = doc.get('author_name') or ['Unknown']
        results.append({
            'title': doc.get('title'),
            'olkey': key,
            'year': doc.get('first_publish_year'),
            'author': author[0],
        })
    return results


def get_or_create_book(olkey, update=False):
    ''' create a book or work '''
    # check if this is in the format of an OL book identifier
    if re.match(r'^OL\d+W$', olkey):
        model = models.Work
    elif re.match(r'^OL\d+M$', olkey):
        model = models.Edition
    else:
        raise ValueError('Invalid OpenLibrary ID')

    # get the existing entry from our db, if it exists
    try:
        book = model.objects.get(openlibrary_key=olkey)
        if not update:
            return book
        # we have the book, but still want to update it from OL
    except ObjectDoesNotExist:
        # no book was found, so we start creating a new one
        book = model(openlibrary_key=olkey)

    # load the book json from openlibrary.org
    response = requests.get('%s/works/%s.json' % (OL_URL, olkey))
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

    # this book sure as heck better be an edition
    if data.get('works'):
        key = data.get('works')[0]['key']
        key = key.split('/')[-1]
        work = get_or_create_book(key)
        book.parent_work = work
    book.save()

    # we also need to know the author get the cover
    for author_blob in data.get('authors'):
        # this id starts as "/authors/OL1234567A" and we want just "OL1234567A"
        author_blob = author_blob.get('author', author_blob)
        author_id = author_blob['key']
        author_id = author_id.split('/')[-1]
        book.authors.add(get_or_create_author(author_id))

    if data.get('covers') and len(data['covers']):
        book.cover.save(*get_cover(data['covers'][0]), save=True)

    return book


def get_cover(cover_id):
    ''' ask openlibrary for the cover '''
    # TODO: get medium and small versions
    image_name = '%s-M.jpg' % cover_id
    url = 'https://covers.openlibrary.org/b/id/%s' % image_name
    response = requests.get(url)
    if not response.ok:
        response.raise_for_status()
    image_content = ContentFile(requests.get(url).content)
    return [image_name, image_content]


def get_or_create_author(olkey, update=False):
    ''' load that author '''
    if not re.match(r'^OL\d+A$', olkey):
        raise ValueError('Invalid OpenLibrary author ID')
    try:
        author = models.Author.objects.get(openlibrary_key=olkey)
        if not update:
            return author
    except ObjectDoesNotExist:
        pass

    response = requests.get('%s/authors/%s.json' % (OL_URL, olkey))
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

