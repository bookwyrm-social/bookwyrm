''' testing import '''
import pathlib

from django.test import TestCase
import responses

from bookwyrm import goodreads_import, models

class GoodreadsImport(TestCase):
    ''' importing from goodreads csv '''
    def setUp(self):
        ''' use a test csv '''
        datafile = pathlib.Path(__file__).parent.joinpath(
            'data/goodreads.csv')
        self.csv = open(datafile, 'r')
        self.user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'password', local=True)


    def test_create_job(self):
        ''' creates the import job entry and checks csv '''
        goodreads_import.create_job(self.user, self.csv, False, 'public')
        import_job = models.ImportJob.objects.get()
        self.assertEqual(import_job.user, self.user)
        self.assertEqual(import_job.include_reviews, False)
        self.assertEqual(import_job.privacy, 'public')

        import_items = models.ImportItem.objects.filter(job=import_job).all()
        self.assertEqual(import_items[0].index, 0)
        self.assertEqual(import_items[0].data['Book Id'], '42036538')
        self.assertEqual(import_items[1].index, 1)
        self.assertEqual(import_items[1].data['Book Id'], '52691223')
        self.assertEqual(import_items[2].index, 2)
        self.assertEqual(import_items[2].data['Book Id'], '28694510')


    @responses.activate
    def test_import_data(self):
        ''' resolve entry '''
