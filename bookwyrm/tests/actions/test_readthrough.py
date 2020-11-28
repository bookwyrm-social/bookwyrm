from django.test import TestCase, Client
from django.utils import timezone
from datetime import datetime

from bookwyrm import view_actions as actions, models

class ReadThrough(TestCase):
    def setUp(self):
        self.client = Client()

        self.work = models.Work.objects.create(
            title='Example Work'
        )

        self.edition = models.Edition.objects.create(
            title='Example Edition',
            parent_work=self.work
        )
        self.work.default_edition = self.edition
        self.work.save()

        self.user = models.User.objects.create()

        self.client.force_login(self.user)

    def test_create_basic_readthrough(self):
        """A basic readthrough doesn't create a progress update"""
        self.assertEqual(self.edition.readthrough_set.count(), 0)

        self.client.post('/start-reading/{}'.format(self.edition.id), {
            'start_date': '2020-11-27',
        })

        readthroughs = self.edition.readthrough_set.all()
        self.assertEqual(len(readthroughs), 1)
        self.assertEqual(readthroughs[0].progressupdate_set.count(), 0)
        self.assertEqual(readthroughs[0].start_date,
            datetime(2020, 11, 27, tzinfo=timezone.utc))
        self.assertEqual(readthroughs[0].pages_read, None)
        self.assertEqual(readthroughs[0].finish_date, None)

    def test_create_progress_readthrough(self):
        self.assertEqual(self.edition.readthrough_set.count(), 0)

        self.client.post('/start-reading/{}'.format(self.edition.id), {
            'start_date': '2020-11-27',
            'pages_read': 50,
        })

        readthroughs = self.edition.readthrough_set.all()
        self.assertEqual(len(readthroughs), 1)
        self.assertEqual(readthroughs[0].start_date,
            datetime(2020, 11, 27, tzinfo=timezone.utc))
        self.assertEqual(readthroughs[0].pages_read, 50)
        self.assertEqual(readthroughs[0].finish_date, None)

        progress_updates = readthroughs[0].progressupdate_set.all()
        self.assertEqual(len(progress_updates), 1)
        self.assertEqual(progress_updates[0].mode, models.ProgressMode.PAGE)
        self.assertEqual(progress_updates[0].progress, 50)
