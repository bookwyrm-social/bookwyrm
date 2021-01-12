''' sending out activities '''
import csv
import json
import pathlib
from unittest.mock import patch

from django.http import JsonResponse
from django.test import TestCase
from django.test.client import RequestFactory
import responses

from bookwyrm import forms, models, outgoing
from bookwyrm.settings import DOMAIN


# pylint: disable=too-many-public-methods
class Outgoing(TestCase):
    ''' sends out activities '''
    def setUp(self):
        ''' we'll need some data '''
        self.factory = RequestFactory()
        with patch('bookwyrm.models.user.set_remote_server'):
            self.remote_user = models.User.objects.create_user(
                'rat', 'rat@email.com', 'ratword',
                local=False,
                remote_id='https://example.com/users/rat',
                inbox='https://example.com/users/rat/inbox',
                outbox='https://example.com/users/rat/outbox',
            )
        self.local_user = models.User.objects.create_user(
            'mouse@local.com', 'mouse@mouse.com', 'mouseword',
            local=True, localname='mouse',
            remote_id='https://example.com/users/mouse',
        )

        datafile = pathlib.Path(__file__).parent.joinpath(
            'data/ap_user.json'
        )
        self.userdata = json.loads(datafile.read_bytes())
        del self.userdata['icon']

        work = models.Work.objects.create(title='Test Work')
        self.book = models.Edition.objects.create(
            title='Example Edition',
            remote_id='https://example.com/book/1',
            parent_work=work
        )
        self.shelf = models.Shelf.objects.create(
            name='Test Shelf',
            identifier='test-shelf',
            user=self.local_user
        )


    def test_outbox(self):
        ''' returns user's statuses '''
        request = self.factory.get('')
        result = outgoing.outbox(request, 'mouse')
        self.assertIsInstance(result, JsonResponse)

    def test_outbox_bad_method(self):
        ''' can't POST to outbox '''
        request = self.factory.post('')
        result = outgoing.outbox(request, 'mouse')
        self.assertEqual(result.status_code, 405)

    def test_outbox_unknown_user(self):
        ''' should 404 for unknown and remote users '''
        request = self.factory.post('')
        result = outgoing.outbox(request, 'beepboop')
        self.assertEqual(result.status_code, 405)
        result = outgoing.outbox(request, 'rat')
        self.assertEqual(result.status_code, 405)

    def test_outbox_privacy(self):
        ''' don't show dms et cetera in outbox '''
        models.Status.objects.create(
            content='PRIVATE!!', user=self.local_user, privacy='direct')
        models.Status.objects.create(
            content='bffs ONLY', user=self.local_user, privacy='followers')
        models.Status.objects.create(
            content='unlisted status', user=self.local_user, privacy='unlisted')
        models.Status.objects.create(
            content='look at this', user=self.local_user, privacy='public')

        request = self.factory.get('')
        result = outgoing.outbox(request, 'mouse')
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.content)
        self.assertEqual(data['type'], 'OrderedCollection')
        self.assertEqual(data['totalItems'], 2)

    def test_outbox_filter(self):
        ''' if we only care about reviews, only get reviews '''
        models.Review.objects.create(
            content='look at this', name='hi', rating=1,
            book=self.book, user=self.local_user)
        models.Status.objects.create(
            content='look at this', user=self.local_user)

        request = self.factory.get('', {'type': 'bleh'})
        result = outgoing.outbox(request, 'mouse')
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.content)
        self.assertEqual(data['type'], 'OrderedCollection')
        self.assertEqual(data['totalItems'], 2)

        request = self.factory.get('', {'type': 'Review'})
        result = outgoing.outbox(request, 'mouse')
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.content)
        self.assertEqual(data['type'], 'OrderedCollection')
        self.assertEqual(data['totalItems'], 1)


    def test_handle_follow(self):
        ''' send a follow request '''
        self.assertEqual(models.UserFollowRequest.objects.count(), 0)

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_follow(self.local_user, self.remote_user)

        rel = models.UserFollowRequest.objects.get()

        self.assertEqual(rel.user_subject, self.local_user)
        self.assertEqual(rel.user_object, self.remote_user)
        self.assertEqual(rel.status, 'follow_request')


    def test_handle_unfollow(self):
        ''' send an unfollow '''
        self.remote_user.followers.add(self.local_user)
        self.assertEqual(self.remote_user.followers.count(), 1)
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_unfollow(self.local_user, self.remote_user)

        self.assertEqual(self.remote_user.followers.count(), 0)


    def test_handle_accept(self):
        ''' accept a follow request '''
        rel = models.UserFollowRequest.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user
        )
        rel_id = rel.id

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_accept(rel)
        # request should be deleted
        self.assertEqual(
            models.UserFollowRequest.objects.filter(id=rel_id).count(), 0
        )
        # follow relationship should exist
        self.assertEqual(self.remote_user.followers.first(), self.local_user)


    def test_handle_reject(self):
        ''' reject a follow request '''
        rel = models.UserFollowRequest.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user
        )
        rel_id = rel.id

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_reject(rel)
        # request should be deleted
        self.assertEqual(
            models.UserFollowRequest.objects.filter(id=rel_id).count(), 0
        )
        # follow relationship should not exist
        self.assertEqual(
            models.UserFollows.objects.filter(id=rel_id).count(), 0
        )

    def test_existing_user(self):
        ''' simple database lookup by username '''
        result = outgoing.handle_remote_webfinger('@mouse@local.com')
        self.assertEqual(result, self.local_user)

        result = outgoing.handle_remote_webfinger('mouse@local.com')
        self.assertEqual(result, self.local_user)


    @responses.activate
    def test_load_user(self):
        ''' find a remote user using webfinger '''
        username = 'mouse@example.com'
        wellknown = {
            "subject": "acct:mouse@example.com",
            "links": [{
                "rel": "self",
                "type": "application/activity+json",
                "href": "https://example.com/user/mouse"
            }]
        }
        responses.add(
            responses.GET,
            'https://example.com/.well-known/webfinger?resource=acct:%s' \
                    % username,
            json=wellknown,
            status=200)
        responses.add(
            responses.GET,
            'https://example.com/user/mouse',
            json=self.userdata,
            status=200)
        with patch('bookwyrm.models.user.set_remote_server.delay'):
            result = outgoing.handle_remote_webfinger('@mouse@example.com')
            self.assertIsInstance(result, models.User)
            self.assertEqual(result.username, 'mouse@example.com')


    def test_handle_shelve(self):
        ''' shelve a book '''
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_shelve(self.local_user, self.book, self.shelf)
        # make sure the book is on the shelf
        self.assertEqual(self.shelf.books.get(), self.book)


    def test_handle_shelve_to_read(self):
        ''' special behavior for the to-read shelf '''
        shelf = models.Shelf.objects.get(identifier='to-read')

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_shelve(self.local_user, self.book, shelf)
        # make sure the book is on the shelf
        self.assertEqual(shelf.books.get(), self.book)


    def test_handle_shelve_reading(self):
        ''' special behavior for the reading shelf '''
        shelf = models.Shelf.objects.get(identifier='reading')

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_shelve(self.local_user, self.book, shelf)
        # make sure the book is on the shelf
        self.assertEqual(shelf.books.get(), self.book)


    def test_handle_shelve_read(self):
        ''' special behavior for the read shelf '''
        shelf = models.Shelf.objects.get(identifier='read')

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_shelve(self.local_user, self.book, shelf)
        # make sure the book is on the shelf
        self.assertEqual(shelf.books.get(), self.book)


    def test_handle_unshelve(self):
        ''' remove a book from a shelf '''
        self.shelf.books.add(self.book)
        self.shelf.save()
        self.assertEqual(self.shelf.books.count(), 1)
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_unshelve(self.local_user, self.book, self.shelf)
        self.assertEqual(self.shelf.books.count(), 0)


    def test_handle_reading_status_to_read(self):
        ''' posts shelve activities '''
        shelf = self.local_user.shelf_set.get(identifier='to-read')
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_reading_status(
                self.local_user, shelf, self.book, 'public')
        status = models.GeneratedNote.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.mention_books.first(), self.book)
        self.assertEqual(status.content, 'wants to read')

    def test_handle_reading_status_reading(self):
        ''' posts shelve activities '''
        shelf = self.local_user.shelf_set.get(identifier='reading')
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_reading_status(
                self.local_user, shelf, self.book, 'public')
        status = models.GeneratedNote.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.mention_books.first(), self.book)
        self.assertEqual(status.content, 'started reading')

    def test_handle_reading_status_read(self):
        ''' posts shelve activities '''
        shelf = self.local_user.shelf_set.get(identifier='read')
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_reading_status(
                self.local_user, shelf, self.book, 'public')
        status = models.GeneratedNote.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.mention_books.first(), self.book)
        self.assertEqual(status.content, 'finished reading')

    def test_handle_reading_status_other(self):
        ''' posts shelve activities '''
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_reading_status(
                self.local_user, self.shelf, self.book, 'public')
        self.assertFalse(models.GeneratedNote.objects.exists())


    def test_handle_imported_book(self):
        ''' goodreads import added a book, this adds related connections '''
        shelf = self.local_user.shelf_set.filter(identifier='read').first()
        self.assertIsNone(shelf.books.first())

        import_job = models.ImportJob.objects.create(user=self.local_user)
        datafile = pathlib.Path(__file__).parent.joinpath('data/goodreads.csv')
        csv_file = open(datafile, 'r')
        for index, entry in enumerate(list(csv.DictReader(csv_file))):
            import_item = models.ImportItem.objects.create(
                job_id=import_job.id, index=index, data=entry, book=self.book)
            break

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_imported_book(
                self.local_user, import_item, False, 'public')

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)

        readthrough = models.ReadThrough.objects.get(user=self.local_user)
        self.assertEqual(readthrough.book, self.book)
        # I can't remember how to create dates and I don't want to look it up.
        self.assertEqual(readthrough.start_date.year, 2020)
        self.assertEqual(readthrough.start_date.month, 10)
        self.assertEqual(readthrough.start_date.day, 21)
        self.assertEqual(readthrough.finish_date.year, 2020)
        self.assertEqual(readthrough.finish_date.month, 10)
        self.assertEqual(readthrough.finish_date.day, 25)


    def test_handle_imported_book_already_shelved(self):
        ''' goodreads import added a book, this adds related connections '''
        shelf = self.local_user.shelf_set.filter(identifier='to-read').first()
        models.ShelfBook.objects.create(
            shelf=shelf, added_by=self.local_user, book=self.book)

        import_job = models.ImportJob.objects.create(user=self.local_user)
        datafile = pathlib.Path(__file__).parent.joinpath('data/goodreads.csv')
        csv_file = open(datafile, 'r')
        for index, entry in enumerate(list(csv.DictReader(csv_file))):
            import_item = models.ImportItem.objects.create(
                job_id=import_job.id, index=index, data=entry, book=self.book)
            break

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_imported_book(
                self.local_user, import_item, False, 'public')

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)
        self.assertIsNone(
            self.local_user.shelf_set.get(identifier='read').books.first())
        readthrough = models.ReadThrough.objects.get(user=self.local_user)
        self.assertEqual(readthrough.book, self.book)
        self.assertEqual(readthrough.start_date.year, 2020)
        self.assertEqual(readthrough.start_date.month, 10)
        self.assertEqual(readthrough.start_date.day, 21)
        self.assertEqual(readthrough.finish_date.year, 2020)
        self.assertEqual(readthrough.finish_date.month, 10)
        self.assertEqual(readthrough.finish_date.day, 25)


    def test_handle_import_twice(self):
        ''' re-importing books '''
        shelf = self.local_user.shelf_set.filter(identifier='read').first()
        import_job = models.ImportJob.objects.create(user=self.local_user)
        datafile = pathlib.Path(__file__).parent.joinpath('data/goodreads.csv')
        csv_file = open(datafile, 'r')
        for index, entry in enumerate(list(csv.DictReader(csv_file))):
            import_item = models.ImportItem.objects.create(
                job_id=import_job.id, index=index, data=entry, book=self.book)
            break

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_imported_book(
                self.local_user, import_item, False, 'public')
            outgoing.handle_imported_book(
                self.local_user, import_item, False, 'public')

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)

        readthrough = models.ReadThrough.objects.get(user=self.local_user)
        self.assertEqual(readthrough.book, self.book)
        # I can't remember how to create dates and I don't want to look it up.
        self.assertEqual(readthrough.start_date.year, 2020)
        self.assertEqual(readthrough.start_date.month, 10)
        self.assertEqual(readthrough.start_date.day, 21)
        self.assertEqual(readthrough.finish_date.year, 2020)
        self.assertEqual(readthrough.finish_date.month, 10)
        self.assertEqual(readthrough.finish_date.day, 25)


    def test_handle_imported_book_review(self):
        ''' goodreads review import '''
        import_job = models.ImportJob.objects.create(user=self.local_user)
        datafile = pathlib.Path(__file__).parent.joinpath('data/goodreads.csv')
        csv_file = open(datafile, 'r')
        entry = list(csv.DictReader(csv_file))[2]
        import_item = models.ImportItem.objects.create(
            job_id=import_job.id, index=0, data=entry, book=self.book)

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_imported_book(
                self.local_user, import_item, True, 'unlisted')
        review = models.Review.objects.get(book=self.book, user=self.local_user)
        self.assertEqual(review.content, 'mixed feelings')
        self.assertEqual(review.rating, 2)
        self.assertEqual(review.published_date.year, 2019)
        self.assertEqual(review.published_date.month, 7)
        self.assertEqual(review.published_date.day, 8)
        self.assertEqual(review.privacy, 'unlisted')


    def test_handle_imported_book_reviews_disabled(self):
        ''' goodreads review import '''
        import_job = models.ImportJob.objects.create(user=self.local_user)
        datafile = pathlib.Path(__file__).parent.joinpath('data/goodreads.csv')
        csv_file = open(datafile, 'r')
        entry = list(csv.DictReader(csv_file))[2]
        import_item = models.ImportItem.objects.create(
            job_id=import_job.id, index=0, data=entry, book=self.book)

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_imported_book(
                self.local_user, import_item, False, 'unlisted')
        self.assertFalse(models.Review.objects.filter(
            book=self.book, user=self.local_user
        ).exists())


    def test_handle_delete_status(self):
        ''' marks a status as deleted '''
        status = models.Status.objects.create(
            user=self.local_user, content='hi')
        self.assertFalse(status.deleted)
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_delete_status(self.local_user, status)
        status.refresh_from_db()
        self.assertTrue(status.deleted)


    def test_handle_favorite(self):
        ''' create and broadcast faving a status '''
        status = models.Status.objects.create(
            user=self.local_user, content='hi')

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_favorite(self.remote_user, status)
        fav = models.Favorite.objects.get()
        self.assertEqual(fav.status, status)
        self.assertEqual(fav.user, self.remote_user)

        notification = models.Notification.objects.get()
        self.assertEqual(notification.notification_type, 'FAVORITE')
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.related_user, self.remote_user)


    def test_handle_unfavorite(self):
        ''' unfav a status '''
        status = models.Status.objects.create(
            user=self.local_user, content='hi')
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_favorite(self.remote_user, status)

        self.assertEqual(models.Favorite.objects.count(), 1)
        self.assertEqual(models.Notification.objects.count(), 1)

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_unfavorite(self.remote_user, status)
        self.assertEqual(models.Favorite.objects.count(), 0)
        self.assertEqual(models.Notification.objects.count(), 0)


    def test_handle_boost(self):
        ''' boost a status '''
        status = models.Status.objects.create(
            user=self.local_user, content='hi')

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_boost(self.remote_user, status)

        boost = models.Boost.objects.get()
        self.assertEqual(boost.boosted_status, status)
        self.assertEqual(boost.user, self.remote_user)
        self.assertEqual(boost.privacy, 'public')

        notification = models.Notification.objects.get()
        self.assertEqual(notification.notification_type, 'BOOST')
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.related_user, self.remote_user)
        self.assertEqual(notification.related_status, status)

    def test_handle_boost_unlisted(self):
        ''' boost a status '''
        status = models.Status.objects.create(
            user=self.local_user, content='hi', privacy='unlisted')

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_boost(self.remote_user, status)

        boost = models.Boost.objects.get()
        self.assertEqual(boost.privacy, 'unlisted')

    def test_handle_boost_private(self):
        ''' boost a status '''
        status = models.Status.objects.create(
            user=self.local_user, content='hi', privacy='followers')

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_boost(self.remote_user, status)
        self.assertFalse(models.Boost.objects.exists())

    def test_handle_boost_twice(self):
        ''' boost a status '''
        status = models.Status.objects.create(
            user=self.local_user, content='hi')

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_boost(self.remote_user, status)
            outgoing.handle_boost(self.remote_user, status)
        self.assertEqual(models.Boost.objects.count(), 1)


    def test_handle_unboost(self):
        ''' undo a boost '''
        status = models.Status.objects.create(
            user=self.local_user, content='hi')
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_boost(self.remote_user, status)

        self.assertEqual(models.Boost.objects.count(), 1)
        self.assertEqual(models.Notification.objects.count(), 1)
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_unboost(self.remote_user, status)
        self.assertEqual(models.Boost.objects.count(), 0)
        self.assertEqual(models.Notification.objects.count(), 0)
