''' generates activitypub formatted objects '''

def shelve_action(user, book, shelf):
    ''' a user puts a book on a shelf.
    activitypub action type Add
    https://www.w3.org/ns/activitystreams#Add '''
    book_title = book.data['title']
    summary = '%s added %s to %s' % (
        user.username,
        book_title,
        shelf.name
    )
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'summary': summary,
        'type': 'Add',
        'actor': user.activitypub_id,
        'object': {
            'type': 'Document',
            'name': book_title,
            'url': book.openlibary_key
        },
        'target': {
            'type': 'Collection',
            'name': shelf.name,
            'id': shelf.activitypub_id
        }
    }

