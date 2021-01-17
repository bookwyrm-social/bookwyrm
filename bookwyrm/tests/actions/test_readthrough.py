from django.test import TestCase, Client
from django.utils import timezone
from datetime import datetime

from bookwyrm import models

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

        self.user = models.User.objects.create_user(
            'cinco', 'cinco@example.com', 'seissiete',
            local=True, localname='cinco')

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
        self.assertEqual(readthroughs[0].progress, None)
        self.assertEqual(readthroughs[0].finish_date, None)

    def test_create_progress_readthrough(self):
        self.assertEqual(self.edition.readthrough_set.count(), 0)

        self.client.post('/start-reading/{}'.format(self.edition.id), {
            'start_date': '2020-11-27',
            'progress': 50,
        })

        readthroughs = self.edition.readthrough_set.all()
        self.assertEqual(len(readthroughs), 1)
        self.assertEqual(readthroughs[0].start_date,
            datetime(2020, 11, 27, tzinfo=timezone.utc))
        self.assertEqual(readthroughs[0].progress, 50)
        self.assertEqual(readthroughs[0].finish_date, None)

        progress_updates = readthroughs[0].progressupdate_set.all()
        self.assertEqual(len(progress_updates), 1)
        self.assertEqual(progress_updates[0].mode, models.ProgressMode.PAGE)
        self.assertEqual(progress_updates[0].progress, 50)

        # Update progress
        self.client.post('/edit-readthrough', {
            'id': readthroughs[0].id,
            'progress': 100,
        })

        progress_updates = readthroughs[0].progressupdate_set\
            .order_by('updated_date').all()
        self.assertEqual(len(progress_updates), 2)
        self.assertEqual(progress_updates[1].mode, models.ProgressMode.PAGE)
        self.assertEqual(progress_updates[1].progress, 100)
