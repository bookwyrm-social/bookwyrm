from django.test import TestCase

from fedireads import models
from fedireads import status as status_builder


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


    def test_comment_from_activity(self):
        activity = {
            "id": "https://example.com/user/mouse/comment/6",
            "url": "https://example.com/user/mouse/comment/6",
            "inReplyTo": None,
            "published": "2020-05-08T23:45:44.768012+00:00",
            "attributedTo": "https://example.com/user/mouse",
            "to": [
                "https://www.w3.org/ns/activitystreams#Public"
            ],
            "cc": [
                "https://example.com/user/mouse/followers"
            ],
            "sensitive": False,
            "content": "commentary",
            "type": "Note",
            "attachment": [],
            "replies": {
                "id": "https://example.com/user/mouse/comment/6/replies",
                "type": "Collection",
                "first": {
                    "type": "CollectionPage",
                    "next": "https://example.com/user/mouse/comment/6/replies?only_other_accounts=true&page=true",
                    "partOf": "https://example.com/user/mouse/comment/6/replies",
                    "items": []
                }
            },
            "inReplyToBook": self.book.remote_id,
            "fedireadsType": "Comment"
        }
        comment = status_builder.create_comment_from_activity(
            self.user, activity)
        self.assertEqual(comment.content, 'commentary')
        self.assertEqual(comment.book, self.book)
        self.assertEqual(
            comment.published_date, '2020-05-08T23:45:44.768012+00:00')
