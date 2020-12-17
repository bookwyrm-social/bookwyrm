''' testing models '''
from dateutil.parser import parse
from django.test import TestCase
from django.utils import timezone

from bookwyrm import models, settings
from bookwyrm.models.book import isbn_10_to_13, isbn_13_to_10


class Book(TestCase):
    ''' not too much going on in the books model but here we are '''
    def setUp(self):
        ''' we'll need some books '''
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
        ''' fanciness with remote/origin ids '''
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


    def test_get_edition_info(self):
        ''' text slug about an edition '''
        book = models.Edition.objects.create(title='Test Edition')
        self.assertEqual(book.edition_info, '')

        book.physical_format = 'worm'
        book.save()
        self.assertEqual(book.edition_info, 'worm')

        book.languages = ['English']
        book.save()
        self.assertEqual(book.edition_info, 'worm')

        book.languages = ['Glorbish', 'English']
        book.save()
        self.assertEqual(book.edition_info, 'worm, Glorbish language')

        book.published_date = timezone.make_aware(parse('2020'))
        book.save()
        self.assertEqual(book.edition_info, 'worm, Glorbish language, 2020')
        self.assertEqual(
            book.alt_text, 'Test Edition cover (worm, Glorbish language, 2020)')
