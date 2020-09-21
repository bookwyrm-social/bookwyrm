''' testing models '''
from django.test import TestCase

from bookwyrm import models, settings


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
        local_id = 'https://%s/book/%d' % (settings.DOMAIN, self.work.id)
        self.assertEqual(self.work.get_remote_id(), local_id)
        self.assertEqual(self.work.remote_id, 'https://example.com/book/1')

    def test_local_id(self):
        ''' the local_id property for books '''
        expected_id = 'https://%s/book/%d' % (settings.DOMAIN, self.work.id)
        self.assertEqual(self.work.local_id, expected_id)

    def test_create_book(self):
        ''' you shouldn't be able to create Books (only editions and works) '''
        self.assertRaises(
            ValueError,
            models.Book.objects.create,
            title='Invalid Book'
        )

    def test_default_edition(self):
        ''' a work should always be able to produce a deafult edition '''
        self.assertIsInstance(self.work.default_edition, models.Edition)
        self.assertEqual(self.work.default_edition, self.first_edition)

        self.second_edition.default = True
        self.second_edition.save()

        self.assertEqual(self.work.default_edition, self.second_edition)


class Shelf(TestCase):
    def setUp(self):
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword')
        models.Shelf.objects.create(
            name='Test Shelf', identifier='test-shelf', user=user)

    def test_remote_id(self):
        ''' editions and works use the same absolute id syntax '''
        shelf = models.Shelf.objects.get(identifier='test-shelf')
        expected_id = 'https://%s/user/mouse/shelf/test-shelf' % settings.DOMAIN
        self.assertEqual(shelf.get_remote_id(), expected_id)
