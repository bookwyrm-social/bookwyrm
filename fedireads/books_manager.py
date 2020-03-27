''' select and call a connector for whatever book task needs doing '''
from fedireads.connectors import OpenLibraryConnector

openlibrary = OpenLibraryConnector()
def get_or_create_book(key):
    ''' pull up a book record by whatever means possible '''
    return openlibrary.get_or_create_book(key)

def search(query):
    ''' ya '''
    return openlibrary.search(query)


def update_book(key):
    return openlibrary.update_book(key)
