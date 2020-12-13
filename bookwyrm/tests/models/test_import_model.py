''' testing models '''
import datetime
from django.utils import timezone
from django.test import TestCase

from bookwyrm import models


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
            'Date Read': '2019/04/12',
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
            'mouse', 'mouse@mouse.mouse', 'mouseword', local=True)
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
        expected = datetime.datetime(2019, 4, 9, 0, 0, tzinfo=timezone.utc)
        item = models.ImportItem.objects.get(index=1)
        self.assertEqual(item.date_added, expected)


    def test_date_read(self):
        ''' converts to the local shelf typology '''
        expected = datetime.datetime(2019, 4, 12, 0, 0, tzinfo=timezone.utc)
        item = models.ImportItem.objects.get(index=2)
        self.assertEqual(item.date_read, expected)


    def test_currently_reading_reads(self):
        expected = [models.ReadThrough(
            start_date=datetime.datetime(2019, 4, 9, 0, 0, tzinfo=timezone.utc))]
        actual = models.ImportItem.objects.get(index=1)
        self.assertEqual(actual.reads[0].start_date, expected[0].start_date)
        self.assertEqual(actual.reads[0].finish_date, expected[0].finish_date)

    def test_read_reads(self):
        actual = models.ImportItem.objects.get(index=2)
        self.assertEqual(actual.reads[0].start_date, datetime.datetime(2019, 4, 9, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(actual.reads[0].finish_date, datetime.datetime(2019, 4, 12, 0, 0, tzinfo=timezone.utc))

    def test_unread_reads(self):
        expected = []
        actual = models.ImportItem.objects.get(index=3)
        self.assertEqual(actual.reads, expected)



