''' federate book data '''
from fedireads.settings import DOMAIN

def get_book(book, recursive=True):
    ''' activitypub serialize a book '''

    fields = [
        'title',
        'sort_title',
        'subtitle',
        'isbn_13',
        'oclc_number',
        'openlibrary_key',
        'librarything_key',
        'lccn',
        'oclc_number',
        'pages',
        'physical_format',
        'misc_identifiers',

        'description',
        'languages',
        'series',
        'series_number',
        'subjects',
        'subject_places',
        'pages',
        'physical_format',
    ]

    book_type = type(book).__name__
    activity = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'type': 'Document',
        'book_type': book_type,
        'name': book.title,
        'url': book.absolute_id,

        'authors': [a.absolute_id for a in book.authors.all()],
        'first_published_date': book.first_published_date.isoformat() if \
                book.first_published_date else None,
        'published_date': book.published_date.isoformat() if \
                book.published_date else None,
    }
    if recursive:
        if book_type == 'Edition':
            activity['work'] = get_book(book.parent_work, recursive=False)
        else:
            editions = book.edition_set.order_by('default')
            activity['editions'] = [
                get_book(b, recursive=False) for b in editions]

    for field in fields:
        if hasattr(book, field):
            activity[field] = book.__getattribute__(field)

    if book.cover:
        image_path = book.cover.url
        image_type = image_path.split('.')[-1]
        activity['attachment'] = [{
            'type': 'Document',
            'mediaType': 'image/%s' % image_type,
            'url': 'https://%s%s' % (DOMAIN, image_path),
            'name': 'Cover of "%s"' % book.title,
        }]
    return {k: v for (k, v) in activity.items() if v}


def get_author(author):
    ''' serialize an author '''
    fields = [
        'name',
        'born',
        'died',
        'aliases',
        'bio'
        'openlibrary_key',
        'wikipedia_link',
    ]
    activity = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'url': author.absolute_id,
        'type': 'Person',
    }
    for field in fields:
        if hasattr(author, field):
            activity[field] = author.__getattribute__(field)
    return activity
