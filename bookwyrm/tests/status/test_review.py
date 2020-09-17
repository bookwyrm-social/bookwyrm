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
