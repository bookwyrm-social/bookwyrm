from django.test import TestCase

from bookwyrm import models, outgoing


class Shelving(TestCase):
    def setUp(self):
        self.user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.com', 'mouseword',
            local=True,
            remote_id='http://local.com/users/mouse',
        )
        self.book = models.Edition.objects.create(
            title='Example Edition',
            remote_id='https://example.com/book/1',
        )
        self.shelf = models.Shelf.objects.create(
            name='Test Shelf',
            identifier='test-shelf',
            user=self.user
        )


    def test_handle_shelve(self):
        outgoing.handle_shelve(self.user, self.book, self.shelf)
        # make sure the book is on the shelf
        self.assertEqual(self.shelf.books.get(), self.book)


    def test_handle_shelve_to_read(self):
        shelf = models.Shelf.objects.get(identifier='to-read')

        outgoing.handle_shelve(self.user, self.book, shelf)
        # make sure the book is on the shelf
        self.assertEqual(shelf.books.get(), self.book)

        # it should have posted a status about this
        status = models.GeneratedStatus.objects.get()
        self.assertEqual(status.content, 'wants to read')
        self.assertEqual(status.user, self.user)
        self.assertEqual(status.mention_books.count(), 1)
        self.assertEqual(status.mention_books.first(), self.book)

        # and it should not create a read-through
        self.assertEqual(models.ReadThrough.objects.count(), 0)


    def test_handle_shelve_reading(self):
        shelf = models.Shelf.objects.get(identifier='reading')

        outgoing.handle_shelve(self.user, self.book, shelf)
        # make sure the book is on the shelf
        self.assertEqual(shelf.books.get(), self.book)

        # it should have posted a status about this
        status = models.GeneratedStatus.objects.order_by('-published_date').first()
        self.assertEqual(status.content, 'started reading')
        self.assertEqual(status.user, self.user)
        self.assertEqual(status.mention_books.count(), 1)
        self.assertEqual(status.mention_books.first(), self.book)

        # and it should create a read-through
        readthrough = models.ReadThrough.objects.get()
        self.assertEqual(readthrough.user, self.user)
        self.assertEqual(readthrough.book.id, self.book.id)
        self.assertIsNotNone(readthrough.start_date)
        self.assertIsNone(readthrough.finish_date)


    def test_handle_shelve_read(self):
        shelf = models.Shelf.objects.get(identifier='read')

        outgoing.handle_shelve(self.user, self.book, shelf)
        # make sure the book is on the shelf
        self.assertEqual(shelf.books.get(), self.book)

        # it should have posted a status about this
        status = models.GeneratedStatus.objects.order_by('-published_date').first()
        self.assertEqual(status.content, 'finished reading')
        self.assertEqual(status.user, self.user)
        self.assertEqual(status.mention_books.count(), 1)
        self.assertEqual(status.mention_books.first(), self.book)

        # and it should update the existing read-through
        readthrough = models.ReadThrough.objects.get()
        self.assertEqual(readthrough.user, self.user)
        self.assertEqual(readthrough.book.id, self.book.id)
        self.assertIsNotNone(readthrough.start_date)
        self.assertIsNotNone(readthrough.finish_date)


    def test_handle_unshelve(self):
        self.shelf.books.add(self.book)
        self.shelf.save()
        self.assertEqual(self.shelf.books.count(), 1)
        outgoing.handle_unshelve(self.user, self.book, self.shelf)
        self.assertEqual(self.shelf.books.count(), 0)
