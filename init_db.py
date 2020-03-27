''' starter data '''
from fedireads.models import Connector, User
from fedireads.books_manager import get_or_create_book

User.objects.create_user('mouse', 'mouse.reeve@gmail.com', 'password123')
User.objects.create_user(
    'rat', 'rat@rat.com', 'ratword',
    manually_approves_followers=True
)

User.objects.get(id=1).followers.add(User.objects.get(id=2))

Connector.objects.create(
    name='OpenLibrary',
    base_url='https://openlibrary.org',
    covers_url='https://covers.openlibrary.org',
    search_url='https://openlibrary.org/search?q=',
    key_name='openlibrary_key',
)


get_or_create_book('OL1715344W')
get_or_create_book('OL102749W')
