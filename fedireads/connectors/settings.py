''' settings book data connectors '''
CONNECTORS = {
    'openlibrary': {
        'KEY_NAME': 'olkey',
        'DB_KEY_FIELD': 'openlibrary_key',
        'POLITENESS_DELAY': 0,
        'MAX_DAILY_QUERIES': -1,
        'BASE_URL': 'https://openlibrary.org',
        'COVERS_URL': 'https://covers.openlibrary.org',
    },
}

''' not implemented yet:
    'librarything': {
        'KEY_NAME': 'ltkey',
        'DB_KEY_FIELD': 'librarything_key',
        'POLITENESS_DELAY': 1,
        'MAX_DAILY_QUERIES': 1000,
        'BASE_URL': 'https://librarything.com',
    },
    'worldcat': {
        'KEY_NAME': 'ocn',
        'DB_KEY_FIELD': 'oclc_number',
        'POLITENESS_DELAY': 0,
        'MAX_DAILY_QUERIES': -1,
        'BASE_URL': 'https://worldcat.org',
    },
'''
