''' starter data '''
from fedireads.books_manager import get_or_create_book
from fedireads.models import Connector, User
from fedireads.settings import DOMAIN

User.objects.create_user('mouse', 'mouse.reeve@gmail.com', 'password123')
User.objects.create_user(
    'rat', 'rat@rat.com', 'ratword',
    manually_approves_followers=True
)

User.objects.get(id=1).followers.add(User.objects.get(id=2))

Connector.objects.create(
    identifier='openlibrary.org',
    connector_file='openlibrary',
    base_url='https://openlibrary.org',
    covers_url='https://covers.openlibrary.org',
    search_url='https://openlibrary.org/search?q=',
    key_name='openlibrary_key',
)

Connector.objects.create(
    identifier=DOMAIN,
    connector_file='fedireads_connector',
    base_url='https://%s/book' % DOMAIN,
    covers_url='https://%s/images/covers' % DOMAIN,
    search_url='https://%s/search?q=' % DOMAIN,
    key_name='openlibrary_key',
    is_self=True
)


get_or_create_book('OL1715344W')
get_or_create_book('OL102749W')
