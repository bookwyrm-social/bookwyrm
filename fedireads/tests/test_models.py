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
        expected_current = [models.ReadThrough(
            start_date=datetime.datetime(2019, 4, 9, 0, 0),
            finish_date=None
        )]
        expected_read = [models.ReadThrough(
            start_date=datetime.datetime(2019, 4, 9, 0, 0),
            finish_date=datetime.datetime(2019, 4, 9, 0, 0),
        )]
        expected_unknown = [models.ReadThrough(
            start_date=None,
            finish_date=None
        )]
        expecteds = [expected_current, expected_read, expected_unknown]

        actuals = [
            models.ImportItem.objects.get(index=1),
            models.ImportItem.objects.get(index=2),
            models.ImportItem.objects.get(index=3),
        ]
        for (expected, actual) in zip(expecteds, actuals):
            actual = actual.reads

            self.assertIsInstance(actual, list)
            self.assertIsInstance(actual, models.ReadThrough)
            self.assertEqual(actual[0].start_date, expected[0].start_date)
            self.assertEqual(actual[0].finish_date, expected[0].finish_date)
