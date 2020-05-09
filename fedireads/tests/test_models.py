''' testing models '''
import datetime

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


class ImportJob(TestCase):
    ''' this is a fancy one!!! '''
    def setUp(self):
        ''' data is from a goodreads export of The Raven Tower '''
        read_data = {
            'Book Id': 39395857,
            'Title': 'The Raven Tower',
            'Author': 'Ann Leckie',
            'Author l-f': 'Leckie, Ann',
            'Additional Authors': '',
            'ISBN': '="0356506991"',
            'ISBN13': '="9780356506999"',
            'My Rating': 0,
            'Average Rating': 4.06,
            'Publisher': 'Orbit',
            'Binding': 'Hardcover',
            'Number of Pages': 416,
            'Year Published': 2019,
            'Original Publication Year': 2019,
            'Date Read': '2019/04/09',
            'Date Added': '2019/04/09',
            'Bookshelves': '',
            'Bookshelves with positions': '',
            'Exclusive Shelf': 'read',
            'My Review': '',
            'Spoiler': '',
            'Private Notes': '',
            'Read Count': 1,
            'Recommended For': '',
            'Recommended By': '',
            'Owned Copies': 0,
            'Original Purchase Date': '',
            'Original Purchase Location': '',
            'Condition': '',
            'Condition Description': '',
            'BCID': ''
        }
        currently_reading_data = read_data.copy()
        currently_reading_data['Exclusive Shelf'] = 'currently-reading'
        currently_reading_data['Date Read'] = ''

        unknown_read_data = currently_reading_data.copy()
        unknown_read_data['Exclusive Shelf'] = 'read'
        unknown_read_data['Date Read'] = ''

        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword')
        job = models.ImportJob.objects.create(user=user)
        models.ImportItem.objects.create(
            job=job, index=1, data=currently_reading_data)
        models.ImportItem.objects.create(
            job=job, index=2, data=read_data)
        models.ImportItem.objects.create(
            job=job, index=3, data=unknown_read_data)


    def test_isbn(self):
        ''' it unquotes the isbn13 field from data '''
        expected = '9780356506999'
        item = models.ImportItem.objects.get(index=1)
        self.assertEqual(item.isbn, expected)


    def test_shelf(self):
        ''' converts to the local shelf typology '''
        expected = 'reading'
        item = models.ImportItem.objects.get(index=1)
        self.assertEqual(item.shelf, expected)


    def test_date_added(self):
        ''' converts to the local shelf typology '''
        expected = datetime.datetime(2019, 4, 9, 0, 0)
        item = models.ImportItem.objects.get(index=1)
        self.assertEqual(item.date_added, expected)


    def test_date_read(self):
        ''' converts to the local shelf typology '''
        expected = datetime.datetime(2019, 4, 9, 0, 0)
        item = models.ImportItem.objects.get(index=2)
        self.assertEqual(item.date_read, expected)


    def test_reads(self):
        ''' various states of reading '''
        # currently reading
        expected = [models.ReadThrough(
            start_date=datetime.datetime(2019, 4, 9, 0, 0))]
        actual = models.ImportItem.objects.get(index=1)
        self.assertEqual(actual.reads[0].start_date, expected[0].start_date)
        self.assertEqual(actual.reads[0].finish_date, expected[0].finish_date)

        # read
        expected = [models.ReadThrough(
            finish_date=datetime.datetime(2019, 4, 9, 0, 0))]
        actual = models.ImportItem.objects.get(index=2)
        self.assertEqual(actual.reads[0].start_date, expected[0].start_date)
        self.assertEqual(actual.reads[0].finish_date, expected[0].finish_date)

        # unknown dates
        expected = []
        actual = models.ImportItem.objects.get(index=3)
        self.assertEqual(actual.reads, expected)


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


class Status(TestCase):
    def setUp(self):
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword')
        book = models.Edition.objects.create(title='Example Edition')

        models.Status.objects.create(user=user, content='Blah blah')
        models.Comment.objects.create(user=user, content='content', book=book)
        models.Quotation.objects.create(
            user=user, content='content', book=book, quote='blah')
        models.Review.objects.create(
            user=user, content='content', book=book, rating=3)

    def test_status(self):
        status = models.Status.objects.first()
        self.assertEqual(status.status_type, 'Note')
        self.assertEqual(status.activity_type, 'Note')
        expected_id = 'https://%s/user/mouse/status/%d' % \
                (settings.DOMAIN, status.id)
        self.assertEqual(status.absolute_id, expected_id)

    def test_comment(self):
        comment = models.Comment.objects.first()
        self.assertEqual(comment.status_type, 'Comment')
        self.assertEqual(comment.activity_type, 'Note')
        expected_id = 'https://%s/user/mouse/comment/%d' % \
                (settings.DOMAIN, comment.id)
        self.assertEqual(comment.absolute_id, expected_id)

    def test_quotation(self):
        quotation = models.Quotation.objects.first()
        self.assertEqual(quotation.status_type, 'Quotation')
        self.assertEqual(quotation.activity_type, 'Note')
        expected_id = 'https://%s/user/mouse/quotation/%d' % \
                (settings.DOMAIN, quotation.id)
        self.assertEqual(quotation.absolute_id, expected_id)

    def test_review(self):
        review = models.Review.objects.first()
        self.assertEqual(review.status_type, 'Review')
        self.assertEqual(review.activity_type, 'Article')
        expected_id = 'https://%s/user/mouse/review/%d' % \
                (settings.DOMAIN, review.id)
        self.assertEqual(review.absolute_id, expected_id)
