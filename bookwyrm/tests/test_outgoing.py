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


    def test_handle_status(self):
        ''' create a status '''
        form = forms.CommentForm({
            'content': 'hi',
            'user': self.local_user.id,
            'book': self.book.id,
            'privacy': 'public',
        })
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_status(self.local_user, form)
        status = models.Comment.objects.get()
        self.assertEqual(status.content, '<p>hi</p>')
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.book, self.book)

    def test_handle_status_reply(self):
        ''' create a status in reply to an existing status '''
        user = models.User.objects.create_user(
            'rat', 'rat@rat.com', 'password', local=True)
        parent = models.Status.objects.create(
            content='parent status', user=self.local_user)
        form = forms.ReplyForm({
            'content': 'hi',
            'user': user.id,
            'reply_parent': parent.id,
            'privacy': 'public',
        })
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_status(user, form)
        status = models.Status.objects.get(user=user)
        self.assertEqual(status.content, '<p>hi</p>')
        self.assertEqual(status.user, user)
        self.assertEqual(
            models.Notification.objects.get().user, self.local_user)

    def test_handle_status_mentions(self):
        ''' @mention a user in a post '''
        user = models.User.objects.create_user(
            'rat@%s' % DOMAIN, 'rat@rat.com', 'password',
            local=True, localname='rat')
        form = forms.CommentForm({
            'content': 'hi @rat',
            'user': self.local_user.id,
            'book': self.book.id,
            'privacy': 'public',
        })

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_status(self.local_user, form)
        status = models.Status.objects.get()
        self.assertEqual(list(status.mention_users.all()), [user])
        self.assertEqual(models.Notification.objects.get().user, user)
        self.assertEqual(
            status.content,
            '<p>hi <a href="%s">@rat</a></p>' % user.remote_id)

    def test_handle_status_reply_with_mentions(self):
        ''' reply to a post with an @mention'ed user '''
        user = models.User.objects.create_user(
            'rat', 'rat@rat.com', 'password',
            local=True, localname='rat')
        form = forms.CommentForm({
            'content': 'hi @rat@example.com',
            'user': self.local_user.id,
            'book': self.book.id,
            'privacy': 'public',
        })

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_status(self.local_user, form)
        status = models.Status.objects.get()

        form = forms.ReplyForm({
            'content': 'right',
            'user': user,
            'privacy': 'public',
            'reply_parent': status.id
        })
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_status(user, form)

        reply = models.Status.replies(status).first()
        self.assertEqual(reply.content, '<p>right</p>')
        self.assertEqual(reply.user, user)
        self.assertTrue(self.remote_user in reply.mention_users.all())
        self.assertTrue(self.local_user in reply.mention_users.all())

    def test_find_mentions(self):
        ''' detect and look up @ mentions of users '''
        user = models.User.objects.create_user(
            'nutria@%s' % DOMAIN, 'nutria@nutria.com', 'password',
            local=True, localname='nutria')
        self.assertEqual(user.username, 'nutria@%s' % DOMAIN)

        self.assertEqual(
            list(outgoing.find_mentions('@nutria'))[0],
            ('@nutria', user)
        )
        self.assertEqual(
            list(outgoing.find_mentions('leading text @nutria'))[0],
            ('@nutria', user)
        )
        self.assertEqual(
            list(outgoing.find_mentions('leading @nutria trailing text'))[0],
            ('@nutria', user)
        )
        self.assertEqual(
            list(outgoing.find_mentions('@rat@example.com'))[0],
            ('@rat@example.com', self.remote_user)
        )

        multiple = list(outgoing.find_mentions('@nutria and @rat@example.com'))
        self.assertEqual(multiple[0], ('@nutria', user))
        self.assertEqual(multiple[1], ('@rat@example.com', self.remote_user))

        with patch('bookwyrm.outgoing.handle_remote_webfinger') as rw:
            rw.return_value = self.local_user
            self.assertEqual(
                list(outgoing.find_mentions('@beep@beep.com'))[0],
                ('@beep@beep.com', self.local_user)
            )
        with patch('bookwyrm.outgoing.handle_remote_webfinger') as rw:
            rw.return_value = None
            self.assertEqual(list(outgoing.find_mentions('@beep@beep.com')), [])

        self.assertEqual(
            list(outgoing.find_mentions('@nutria@%s' % DOMAIN))[0],
            ('@nutria@%s' % DOMAIN, user)
        )

    def test_format_links(self):
        ''' find and format urls into a tags '''
        url = 'http://www.fish.com/'
        self.assertEqual(
            outgoing.format_links(url),
            '<a href="%s">www.fish.com/</a>' % url)
        url = 'https://archive.org/details/dli.granth.72113/page/n25/mode/2up'
        self.assertEqual(
            outgoing.format_links(url),
            '<a href="%s">' \
                'archive.org/details/dli.granth.72113/page/n25/mode/2up</a>' \
                % url)
        url = 'https://openlibrary.org/search' \
               '?q=arkady+strugatsky&mode=everything'
        self.assertEqual(
            outgoing.format_links(url),
            '<a href="%s">openlibrary.org/search' \
                '?q=arkady+strugatsky&mode=everything</a>' % url)
