''' style fixes and lookups for templates '''
import re
from unittest.mock import patch

from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.utils import timezone

from bookwyrm import models
from bookwyrm.templatetags import bookwyrm_tags


class TemplateTags(TestCase):
    ''' lotta different things here '''
    def setUp(self):
        ''' create some filler objects '''
        self.user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword', local=True)
        with patch('bookwyrm.models.user.set_remote_server.delay'):
            self.remote_user = models.User.objects.create_user(
                'rat', 'rat@rat.rat', 'ratword',
                remote_id='http://example.com/rat', local=False)
        self.book = models.Edition.objects.create(title='Test Book')


    def test_dict_key(self):
        ''' just getting a value out of a dict '''
        test_dict = {'a': 1, 'b': 3}
        self.assertEqual(
            bookwyrm_tags.dict_key(test_dict, 'a'), 1)
        self.assertEqual(
            bookwyrm_tags.dict_key(test_dict, 'c'), 0)


    def test_get_rating(self):
        ''' get a user's most recent rating of a book '''
        models.Review.objects.create(
            user=self.user, book=self.book, rating=3)
        self.assertEqual(
            bookwyrm_tags.get_rating(self.book, self.user), 3)


    def test_get_rating_doesnt_exist(self):
        ''' there is no rating available '''
        self.assertEqual(
            bookwyrm_tags.get_rating(self.book, self.user), 0)


    def test_get_user_identifer_local(self):
        ''' fall back to the simplest uid available '''
        self.assertNotEqual(self.user.username, self.user.localname)
        self.assertEqual(
            bookwyrm_tags.get_user_identifier(self.user), 'mouse')

    def test_get_user_identifer_remote(self):
        ''' for a remote user, should be their full username '''
        self.assertEqual(
            bookwyrm_tags.get_user_identifier(self.remote_user),
            'rat@example.com')

    def test_get_notification_count(self):
        ''' just countin' '''
        self.assertEqual(bookwyrm_tags.get_notification_count(self.user), 0)

        models.Notification.objects.create(
            user=self.user, notification_type='FOLLOW')
        models.Notification.objects.create(
            user=self.user, notification_type='FOLLOW')

        models.Notification.objects.create(
            user=self.remote_user, notification_type='FOLLOW')

        self.assertEqual(bookwyrm_tags.get_notification_count(self.user), 2)


    def test_get_replies(self):
        ''' direct replies to a status '''
        parent = models.Review.objects.create(
            user=self.user, book=self.book)
        first_child = models.Status.objects.create(
            reply_parent=parent, user=self.user)
        second_child = models.Status.objects.create(
            reply_parent=parent, user=self.user)
        third_child = models.Status.objects.create(
            reply_parent=parent, user=self.user, deleted=True)

        replies = bookwyrm_tags.get_replies(parent)
        self.assertEqual(len(replies), 2)
        self.assertTrue(first_child in replies)
        self.assertTrue(second_child in replies)
        self.assertFalse(third_child in replies)


    def test_get_parent(self):
        ''' get the reply parent of a status '''
        parent = models.Review.objects.create(
            user=self.user, book=self.book)
        child = models.Status.objects.create(
            reply_parent=parent, user=self.user)

        result = bookwyrm_tags.get_parent(child)
        self.assertEqual(result, parent)
        self.assertIsInstance(result, models.Review)


    def test_get_user_liked(self):
        ''' did a user like a status '''
        status = models.Review.objects.create(
            user=self.remote_user, book=self.book)

        self.assertFalse(bookwyrm_tags.get_user_liked(self.user, status))
        models.Favorite.objects.create(
            user=self.user,
            status=status
        )
        self.assertTrue(bookwyrm_tags.get_user_liked(self.user, status))


    def test_get_user_boosted(self):
        ''' did a user boost a status '''
        status = models.Review.objects.create(
            user=self.remote_user, book=self.book)

        self.assertFalse(bookwyrm_tags.get_user_boosted(self.user, status))
        models.Boost.objects.create(
            user=self.user,
            boosted_status=status
        )
        self.assertTrue(bookwyrm_tags.get_user_boosted(self.user, status))


    def test_follow_request_exists(self):
        ''' does a user want to follow '''
        self.assertFalse(
            bookwyrm_tags.follow_request_exists(self.user, self.remote_user))

        models.UserFollowRequest.objects.create(
            user_subject=self.user,
            user_object=self.remote_user)

        self.assertFalse(
            bookwyrm_tags.follow_request_exists(self.user, self.remote_user))
        self.assertTrue(
            bookwyrm_tags.follow_request_exists(self.remote_user, self.user))


    def test_get_boosted(self):
        ''' load a boosted status '''
        status = models.Review.objects.create(
            user=self.remote_user, book=self.book)
        boost = models.Boost.objects.create(
            user=self.user,
            boosted_status=status
        )
        boosted = bookwyrm_tags.get_boosted(boost)
        self.assertIsInstance(boosted, models.Review)
        self.assertEqual(boosted, status)


    def test_get_book_description(self):
        ''' grab it from the edition or the parent '''
        work = models.Work.objects.create(title='Test Work')
        self.book.parent_work = work
        self.book.save()

        self.assertIsNone(bookwyrm_tags.get_book_description(self.book))

        work.description = 'hi'
        work.save()
        self.assertEqual(bookwyrm_tags.get_book_description(self.book), 'hi')

        self.book.description = 'hello'
        self.book.save()
        self.assertEqual(bookwyrm_tags.get_book_description(self.book), 'hello')


    def test_get_uuid(self):
        ''' uuid functionality '''
        uuid = bookwyrm_tags.get_uuid('hi')
        self.assertTrue(re.match(r'hi[A-Za-z0-9\-]', uuid))


    def test_time_since(self):
        ''' ultraconcise timestamps '''
        self.assertEqual(bookwyrm_tags.time_since('bleh'), '')

        now = timezone.now()
        self.assertEqual(bookwyrm_tags.time_since(now), '0s')

        seconds_ago = now - relativedelta(seconds=4)
        self.assertEqual(bookwyrm_tags.time_since(seconds_ago), '4s')

        minutes_ago = now - relativedelta(minutes=8)
        self.assertEqual(bookwyrm_tags.time_since(minutes_ago), '8m')

        hours_ago = now - relativedelta(hours=9)
        self.assertEqual(bookwyrm_tags.time_since(hours_ago), '9h')

        days_ago = now - relativedelta(days=3)
        self.assertEqual(bookwyrm_tags.time_since(days_ago), '3d')

        # I am not going to figure out how to mock dates tonight.
        months_ago = now - relativedelta(months=5)
        self.assertTrue(re.match(
            r'[A-Z][a-z]{2} \d?\d',
            bookwyrm_tags.time_since(months_ago)
        ))

        years_ago = now - relativedelta(years=10)
        self.assertTrue(re.match(
            r'[A-Z][a-z]{2} \d?\d \d{4}',
            bookwyrm_tags.time_since(years_ago)
        ))
