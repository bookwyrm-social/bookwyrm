''' Routine tasks for keeping your library tidy '''
from datetime import timedelta
from django.utils import timezone
from fedireads import books_manager
from fedireads import models

def sync_book_data():
    ''' update books with any changes to their canonical source '''
    expiry = timezone.now() - timedelta(days=1)
    books = models.Book.objects.filter(
        sync=True,
        last_sync_date__lte=expiry
    ).all()
    for book in books:
        # TODO: create background tasks
        books_manager.update_book(book)

