from fedireads.models import User
from fedireads.openlibrary import get_or_create_book

User.objects.create_user('mouse', 'mouse.reeve@gmail.com', 'password123')
User.objects.create_user('rat', 'rat@rat.com', 'ratword')

User.objects.get(id=1).followers.add(User.objects.get(id=2))

get_or_create_book('OL1715344W')
get_or_create_book('OL102749W')
