''' testing models '''
from django.test import TestCase

from bookwyrm import models, settings


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
        expected_id = 'https://%s/user/mouse/status/%d' % \
                (settings.DOMAIN, status.id)
        self.assertEqual(status.remote_id, expected_id)

    def test_comment(self):
        comment = models.Comment.objects.first()
        expected_id = 'https://%s/user/mouse/comment/%d' % \
                (settings.DOMAIN, comment.id)
        self.assertEqual(comment.remote_id, expected_id)

    def test_quotation(self):
        quotation = models.Quotation.objects.first()
        expected_id = 'https://%s/user/mouse/quotation/%d' % \
                (settings.DOMAIN, quotation.id)
        self.assertEqual(quotation.remote_id, expected_id)

    def test_review(self):
        review = models.Review.objects.first()
        expected_id = 'https://%s/user/mouse/review/%d' % \
                (settings.DOMAIN, review.id)
        self.assertEqual(review.remote_id, expected_id)


class Tag(TestCase):
    def test_tag(self):
        book = models.Edition.objects.create(title='Example Edition')
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword')
        tag = models.Tag.objects.create(user=user, book=book, name='t/est tag')
        self.assertEqual(tag.identifier, 't%2Fest+tag')

