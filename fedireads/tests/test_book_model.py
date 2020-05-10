''' testing models '''
from django.test import TestCase

from fedireads import models, settings


class Book(TestCase):
    ''' not too much going on in the books model but here we are '''
    def setUp(self):
        work = models.Work.objects.create(title='Example Work')
        models.Edition.objects.create(title='Example Edition', parent_work=work)

    def test_absolute_id(self):
        ''' editions and works use the same absolute id syntax '''
        book = models.Edition.objects.first()
        expected_id = 'https://%s/book/%d' % (settings.DOMAIN, book.id)
        self.assertEqual(book.absolute_id, expected_id)

    def test_create_book(self):
        ''' you shouldn't be able to create Books (only editions and works) '''
        self.assertRaises(
            ValueError,
            models.Book.objects.create,
            title='Invalid Book'
        )

    def test_default_edition(self):
        ''' a work should always be able to produce a deafult edition '''
        default_edition = models.Work.objects.first().default_edition
        self.assertIsInstance(default_edition, models.Edition)


class Shelf(TestCase):
    def setUp(self):
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword')
        models.Shelf.objects.create(
            name='Test Shelf', identifier='test-shelf', user=user)

    def test_absolute_id(self):
        ''' editions and works use the same absolute id syntax '''
        shelf = models.Shelf.objects.get(identifier='test-shelf')
        expected_id = 'https://%s/user/mouse/shelf/test-shelf' % settings.DOMAIN
        self.assertEqual(shelf.absolute_id, expected_id)
