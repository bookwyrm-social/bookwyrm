''' federate book data '''
from fedireads.settings import DOMAIN

def get_book(book):
    ''' activitypub serialize a book '''

    activity = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'type': 'Document',
        'book_type': type(book).__name__,
        'name': book.title,
        'url': book.absolute_id,

        'sort_title': book.sort_title,
        'subtitle': book.subtitle,

        'openlibrary_key': book.openlibrary_key,
        'librarything_key': book.librarything_key,
        'fedireads_key': book.fedireads_key,
        'misc_identifiers': book.misc_identifiers,

        'source_url': book.source_url,
        'sync': book.sync,
        'last_sync_date': book.last_sync_date,

        'description': book.description,
        'language': book.language,
        'series': book.series,
        'series_number': book.series_number,
        'first_published_date': book.first_published_date.isoformat() if \
                book.first_published_date else None,
        'published_date': book.published_date.isoformat() if \
                book.published_date else None,
        'parent_work': book.parent_work.absolute_id if \
                book.parent_work else None,
        'authors': [get_author(a) for a in book.authors.all()],
    }

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
    return {
        'name': author.name,
        'url': author.absolute_id,
    }
