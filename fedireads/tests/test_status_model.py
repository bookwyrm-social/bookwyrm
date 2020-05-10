''' testing models '''
from django.test import TestCase

from fedireads import models, settings


class Status(TestCase):
    def setUp(self):
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword')
        book = models.Edition.objects.create(title='Example Edition')

        models.Status.objects.create(user=user, content='Blah blah')
        models.Comment.objects.create(user=user, content='content', book=book)
        models.Quotation.objects.create(
            user=user, content='content', book=book, quote='blah')
        models.Review.objects.create(
            user=user, content='content', book=book, rating=3)

    def test_status(self):
        status = models.Status.objects.first()
        self.assertEqual(status.status_type, 'Note')
        self.assertEqual(status.activity_type, 'Note')
        expected_id = 'https://%s/user/mouse/status/%d' % \
                (settings.DOMAIN, status.id)
        self.assertEqual(status.absolute_id, expected_id)

    def test_comment(self):
        comment = models.Comment.objects.first()
        self.assertEqual(comment.status_type, 'Comment')
        self.assertEqual(comment.activity_type, 'Note')
        expected_id = 'https://%s/user/mouse/comment/%d' % \
                (settings.DOMAIN, comment.id)
        self.assertEqual(comment.absolute_id, expected_id)

    def test_quotation(self):
        quotation = models.Quotation.objects.first()
        self.assertEqual(quotation.status_type, 'Quotation')
        self.assertEqual(quotation.activity_type, 'Note')
        expected_id = 'https://%s/user/mouse/quotation/%d' % \
                (settings.DOMAIN, quotation.id)
        self.assertEqual(quotation.absolute_id, expected_id)

    def test_review(self):
        review = models.Review.objects.first()
        self.assertEqual(review.status_type, 'Review')
        self.assertEqual(review.activity_type, 'Article')
        expected_id = 'https://%s/user/mouse/review/%d' % \
                (settings.DOMAIN, review.id)
        self.assertEqual(review.absolute_id, expected_id)


class Tag(TestCase):
    def test_tag(self):
        book = models.Edition.objects.create(title='Example Edition')
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword')
        tag = models.Tag.objects.create(user=user, book=book, name='t/est tag')
        self.assertEqual(tag.identifier, 't%2Fest+tag')

