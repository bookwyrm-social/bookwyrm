from django.test import TestCase
import json
import pathlib

from fedireads import activitypub, models
from fedireads import status as status_builder


class Quotation(TestCase):
    ''' we have hecka ways to create statuses '''
    def setUp(self):
        self.user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword',
            remote_id='https://example.com/user/mouse'
        )
        self.book = models.Edition.objects.create(
            title='Example Edition',
            remote_id='https://example.com/book/1',
        )


    def test_create_quotation(self):
        quotation = status_builder.create_quotation(
            self.user, self.book, 'commentary', 'a quote')
        self.assertEqual(quotation.quote, 'a quote')
        self.assertEqual(quotation.content, 'commentary')


    def test_quotation_from_activity(self):
        datafile = pathlib.Path(__file__).parent.joinpath(
            'data/ap_quotation.json'
        )
        status_data = json.loads(datafile.read_bytes())

        quotation = activitypub.Quotation(**status_data)
        self.assertEqual(quotation.content, 'commentary')
        self.assertEqual(quotation.quote, 'quote body')
        self.assertEqual(quotation.book, self.book)
        self.assertEqual(
            quotation.published_date, '2020-05-10T02:38:31.150343+00:00')
