from fedireads.models import User
from fedireads.books_manager import get_or_create_book

User.objects.create_user('mouse', 'mouse.reeve@gmail.com', 'password123')
User.objects.create_user('rat', 'rat@rat.com', 'ratword', manually_approves_followers=True)

User.objects.get(id=1).followers.add(User.objects.get(id=2))

get_or_create_book('OL1715344W')
get_or_create_book('OL102749W')
