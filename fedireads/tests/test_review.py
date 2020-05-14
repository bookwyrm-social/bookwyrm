from django.test import TestCase

from fedireads import models
from fedireads import status as status_builder


class Review(TestCase):
    ''' we have hecka ways to create statuses '''
    def setUp(self):
        self.user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword')
        self.book = models.Edition.objects.create(title='Example Edition')


    def test_create_review(self):
        review = status_builder.create_review(
            self.user, self.book, 'review name', 'content', 5)
        self.assertEqual(review.name, 'review name')
        self.assertEqual(review.content, 'content')
        self.assertEqual(review.rating, 5)

        review = status_builder.create_review(
            self.user, self.book, '<div>review</div> name', '<b>content', 5)
        self.assertEqual(review.name, 'review name')
        self.assertEqual(review.content, 'content')
        self.assertEqual(review.rating, 5)

    def test_review_rating(self):
        review = status_builder.create_review(
            self.user, self.book, 'review name', 'content', -1)
        self.assertEqual(review.name, 'review name')
        self.assertEqual(review.content, 'content')
        self.assertEqual(review.rating, None)

        review = status_builder.create_review(
            self.user, self.book, 'review name', 'content', 6)
        self.assertEqual(review.name, 'review name')
        self.assertEqual(review.content, 'content')
        self.assertEqual(review.rating, None)


    def test_review_from_activity(self):
        activity = {
            'id': 'https://example.com/user/mouse/review/9',
            'url': 'https://example.com/user/mouse/review/9',
            'inReplyTo': None,
            'published': '2020-05-04T00:00:00.000000+00:00',
            'attributedTo': 'https://example.com/user/mouse',
            'to': [
                'https://www.w3.org/ns/activitystreams#Public'
                ],
            'cc': [
                'https://example.com/user/mouse/followers'
                ],
            'sensitive': False,
            'content': 'review content',
            'type': 'Article',
            'attachment': [],
            'replies': {
                'id': 'https://example.com/user/mouse/review/9/replies',
                'type': 'Collection',
                'first': {
                    'type': 'CollectionPage',
                    'next': 'https://example.com/user/mouse/review/9/replies?only_other_accounts=true&page=true',
                    'partOf': 'https://example.com/user/mouse/review/9/replies',
                    'items': []
                    }
                },
            'inReplyToBook': self.book.remote_id,
            'fedireadsType': 'Review',
            'name': 'review title',
            'rating': 3
        }
        review = status_builder.create_review_from_activity(
            self.user, activity)
        self.assertEqual(review.content, 'review content')
        self.assertEqual(review.name, 'review title')
        self.assertEqual(review.rating, 3)
        self.assertEqual(review.book, self.book)
        self.assertEqual(
            review.published_date, '2020-05-04T00:00:00.000000+00:00')
