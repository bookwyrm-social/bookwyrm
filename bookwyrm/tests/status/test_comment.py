from django.test import TestCase

from bookwyrm import models
from bookwyrm import status as status_builder


class Comment(TestCase):
    ''' we have hecka ways to create statuses '''
    def setUp(self):
        self.user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword')
        self.book = models.Edition.objects.create(title='Example Edition')


    def test_create_comment(self):
        comment = status_builder.create_comment(
            self.user, self.book, 'commentary')
        self.assertEqual(comment.content, 'commentary')
