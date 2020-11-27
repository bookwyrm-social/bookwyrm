from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models, outgoing


class Shelving(TestCase):
    def setUp(self):
        self.user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.com', 'mouseword',
            local=True,
            remote_id='http://local.com/users/mouse',
        )
        work = models.Work.objects.create(
            title='Example work',
        )
        self.book = models.Edition.objects.create(
            title='Example Edition',
            remote_id='https://example.com/book/1',
            parent_work=work,
        )
        self.shelf = models.Shelf.objects.create(
            name='Test Shelf',
            identifier='test-shelf',
            user=self.user
        )


    def test_handle_shelve(self):
        with patch('bookwyrm.broadcast.broadcast_task.delay') as _:
            outgoing.handle_shelve(self.user, self.book, self.shelf)
        # make sure the book is on the shelf
        self.assertEqual(self.shelf.books.get(), self.book)


    def test_handle_shelve_to_read(self):
        shelf = models.Shelf.objects.get(identifier='to-read')

        with patch('bookwyrm.broadcast.broadcast_task.delay') as _:
            outgoing.handle_shelve(self.user, self.book, shelf)
        # make sure the book is on the shelf
        self.assertEqual(shelf.books.get(), self.book)


    def test_handle_shelve_reading(self):
        shelf = models.Shelf.objects.get(identifier='reading')

        with patch('bookwyrm.broadcast.broadcast_task.delay') as _:
            outgoing.handle_shelve(self.user, self.book, shelf)
        # make sure the book is on the shelf
        self.assertEqual(shelf.books.get(), self.book)


    def test_handle_shelve_read(self):
        shelf = models.Shelf.objects.get(identifier='read')

        with patch('bookwyrm.broadcast.broadcast_task.delay') as _:
            outgoing.handle_shelve(self.user, self.book, shelf)
        # make sure the book is on the shelf
        self.assertEqual(shelf.books.get(), self.book)


    def test_handle_unshelve(self):
        self.shelf.books.add(self.book)
        self.shelf.save()
        self.assertEqual(self.shelf.books.count(), 1)
        with patch('bookwyrm.broadcast.broadcast_task.delay') as _:
            outgoing.handle_unshelve(self.user, self.book, self.shelf)
        self.assertEqual(self.shelf.books.count(), 0)
