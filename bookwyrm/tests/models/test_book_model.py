''' testing models '''
from django.test import TestCase

from bookwyrm import models, settings
from bookwyrm.models.book import isbn_10_to_13, isbn_13_to_10


class Book(TestCase):
    ''' not too much going on in the books model but here we are '''
    def setUp(self):
        self.work = models.Work.objects.create(
            title='Example Work',
            remote_id='https://example.com/book/1'
        )
        self.first_edition = models.Edition.objects.create(
            title='Example Edition',
            parent_work=self.work,
        )
        self.second_edition = models.Edition.objects.create(
            title='Another Example Edition',
            parent_work=self.work,
        )

    def test_remote_id(self):
        remote_id = 'https://%s/book/%d' % (settings.DOMAIN, self.work.id)
        self.assertEqual(self.work.get_remote_id(), remote_id)
        self.assertEqual(self.work.remote_id, remote_id)

    def test_create_book(self):
        ''' you shouldn't be able to create Books (only editions and works) '''
        self.assertRaises(
            ValueError,
            models.Book.objects.create,
            title='Invalid Book'
        )

    def test_isbn_10_to_13(self):
        ''' checksums and so on '''
        isbn_10 = '178816167X'
        isbn_13 = isbn_10_to_13(isbn_10)
        self.assertEqual(isbn_13, '9781788161671')

        isbn_10 = '1-788-16167-X'
        isbn_13 = isbn_10_to_13(isbn_10)
        self.assertEqual(isbn_13, '9781788161671')


    def test_isbn_13_to_10(self):
        ''' checksums and so on '''
        isbn_13 = '9781788161671'
        isbn_10 = isbn_13_to_10(isbn_13)
        self.assertEqual(isbn_10, '178816167X')

        isbn_13 = '978-1788-16167-1'
        isbn_10 = isbn_13_to_10(isbn_13)
        self.assertEqual(isbn_10, '178816167X')


class Shelf(TestCase):
    def setUp(self):
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword', local=True)
        models.Shelf.objects.create(
            name='Test Shelf', identifier='test-shelf', user=user)

    def test_remote_id(self):
        ''' editions and works use the same absolute id syntax '''
        shelf = models.Shelf.objects.get(identifier='test-shelf')
        expected_id = 'https://%s/user/mouse/shelf/test-shelf' % settings.DOMAIN
        self.assertEqual(shelf.get_remote_id(), expected_id)
