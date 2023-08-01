""" test for app action functionality """
import json
from unittest.mock import patch
from django.core.exceptions import PermissionDenied
from django.test import TestCase, TransactionTestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.views.status import find_mentions, find_or_create_hashtags
from bookwyrm.settings import DOMAIN

from bookwyrm.tests.validate_html import validate_html

# pylint: disable=invalid-name
@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
class StatusTransactions(TransactionTestCase):
    """Test full database transactions"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
            self.another_user = models.User.objects.create_user(
                f"nutria@{DOMAIN}",
                "nutria@nutria.com",
                "password",
                local=True,
                localname="nutria",
            )

        work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )

    def test_create_status_saves(self, *_):
        """This view calls save multiple times"""
        view = views.CreateStatus.as_view()
        form = forms.CommentForm(
            {
                "content": "hi",
                "user": self.local_user.id,
                "book": self.book.id,
                "privacy": "public",
            }
        )
        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch("bookwyrm.activitystreams.add_status_task.apply_async") as mock:
            view(request, "comment")

        self.assertEqual(mock.call_count, 2)


@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.lists_stream.populate_lists_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
# pylint: disable=too-many-public-methods
class StatusViews(TestCase):
    """viewing and creating statuses"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
            self.another_user = models.User.objects.create_user(
                f"nutria@{DOMAIN}",
                "nutria@nutria.com",
                "password",
                local=True,
                localname="nutria",
            )
            self.existing_hashtag = models.Hashtag.objects.create(name="#existing")
        with patch("bookwyrm.models.user.set_remote_server"):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@email.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )

        work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )
        models.SiteSettings.objects.create()

    def test_create_status_comment(self, *_):
        """create a status"""
        view = views.CreateStatus.as_view()
        form = forms.CommentForm(
            {
                "content": "hi",
                "user": self.local_user.id,
                "book": self.book.id,
                "privacy": "public",
            }
        )
        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request, "comment")

        status = models.Comment.objects.get()
        self.assertEqual(status.raw_content, "hi")
        self.assertEqual(status.content, "<p>hi</p>")
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.book, self.book)
        self.assertIsNone(status.edited_date)

    def test_create_status_rating(self, *_):
        """create a status"""
        view = views.CreateStatus.as_view()
        form = forms.RatingForm(
            {
                "user": self.local_user.id,
                "rating": 4,
                "book": self.book.id,
                "privacy": "public",
            }
        )
        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request, "rating")

        status = models.ReviewRating.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.book, self.book)
        self.assertEqual(status.rating, 4.0)
        self.assertIsNone(status.edited_date)

    def test_create_status_wrong_user(self, *_):
        """You can't compose statuses for someone else"""
        view = views.CreateStatus.as_view()
        form = forms.CommentForm(
            {
                "content": "hi",
                "user": self.remote_user.id,
                "book": self.book.id,
                "privacy": "public",
            }
        )
        request = self.factory.post("", form.data)
        request.user = self.local_user
        with self.assertRaises(PermissionDenied):
            view(request, "comment")

    def test_create_status_reply(self, *_):
        """create a status in reply to an existing status"""
        view = views.CreateStatus.as_view()
        user = models.User.objects.create_user(
            "rat", "rat@rat.com", "password", local=True
        )
        parent = models.Status.objects.create(
            content="parent status", user=self.local_user
        )
        form = forms.ReplyForm(
            {
                "content": "hi",
                "user": user.id,
                "reply_parent": parent.id,
                "privacy": "public",
            }
        )
        request = self.factory.post("", form.data)
        request.user = user

        view(request, "reply")

        status = models.Status.objects.get(user=user)
        self.assertEqual(status.content, "<p>hi</p>")
        self.assertEqual(status.user, user)
        self.assertEqual(models.Notification.objects.get().user, self.local_user)

    def test_create_status_mentions(self, *_):
        """@mention a user in a post"""
        view = views.CreateStatus.as_view()
        user = models.User.objects.create_user(
            f"rat@{DOMAIN}",
            "rat@rat.com",
            "password",
            local=True,
            localname="rat",
        )
        form = forms.CommentForm(
            {
                "content": "hi @rat",
                "user": self.local_user.id,
                "book": self.book.id,
                "privacy": "public",
            }
        )
        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request, "comment")

        status = models.Status.objects.get()
        self.assertEqual(list(status.mention_users.all()), [user])
        self.assertEqual(models.Notification.objects.get().user, user)
        self.assertEqual(
            status.content, f'<p>hi <a href="{user.remote_id}">@rat</a></p>'
        )

    def test_create_status_reply_with_mentions(self, *_):
        """reply to a post with an @mention'd user"""
        view = views.CreateStatus.as_view()
        user = models.User.objects.create_user(
            "rat", "rat@rat.com", "password", local=True, localname="rat"
        )
        form = forms.CommentForm(
            {
                "content": "hi @rat@example.com",
                "user": self.local_user.id,
                "book": self.book.id,
                "privacy": "public",
            }
        )
        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request, "comment")
        status = models.Status.objects.get()

        form = forms.ReplyForm(
            {
                "content": "right",
                "user": user.id,
                "privacy": "public",
                "reply_parent": status.id,
            }
        )
        request = self.factory.post("", form.data)
        request.user = user

        view(request, "reply")

        reply = models.Status.replies(status).first()
        self.assertEqual(reply.content, "<p>right</p>")
        self.assertEqual(reply.user, user)
        # the mentioned user in the parent post is only included if @'ed
        self.assertFalse(self.remote_user in reply.mention_users.all())
        self.assertTrue(self.local_user in reply.mention_users.all())

    def test_find_mentions_local(self, *_):
        """detect and look up @ mentions of users"""
        result = find_mentions(self.local_user, "@nutria")
        self.assertEqual(result["@nutria"], self.another_user)
        self.assertEqual(result[f"@nutria@{DOMAIN}"], self.another_user)

        result = find_mentions(self.local_user, f"@nutria@{DOMAIN}")
        self.assertEqual(result["@nutria"], self.another_user)
        self.assertEqual(result[f"@nutria@{DOMAIN}"], self.another_user)

        result = find_mentions(self.local_user, "leading text @nutria")
        self.assertEqual(result["@nutria"], self.another_user)
        self.assertEqual(result[f"@nutria@{DOMAIN}"], self.another_user)

        result = find_mentions(self.local_user, "leading @nutria trailing")
        self.assertEqual(result["@nutria"], self.another_user)
        self.assertEqual(result[f"@nutria@{DOMAIN}"], self.another_user)

        self.assertEqual(find_mentions(self.local_user, "leading@nutria"), {})

    def test_find_mentions_remote(self, *_):
        """detect and look up @ mentions of users"""
        self.assertEqual(
            find_mentions(self.local_user, "@rat@example.com"),
            {"@rat@example.com": self.remote_user},
        )

    def test_find_mentions_multiple(self, *_):
        """detect and look up @ mentions of users"""
        multiple = find_mentions(self.local_user, "@nutria and @rat@example.com")
        self.assertEqual(multiple["@nutria"], self.another_user)
        self.assertEqual(multiple[f"@nutria@{DOMAIN}"], self.another_user)
        self.assertEqual(multiple["@rat@example.com"], self.remote_user)
        self.assertIsNone(multiple.get("@rat"))

    def test_find_mentions_unknown(self, *_):
        """detect and look up @ mentions of users"""
        multiple = find_mentions(self.local_user, "@nutria and @rdkjfgh")
        self.assertEqual(multiple["@nutria"], self.another_user)
        self.assertEqual(multiple[f"@nutria@{DOMAIN}"], self.another_user)

    def test_find_mentions_blocked(self, *_):
        """detect and look up @ mentions of users"""
        self.another_user.blocks.add(self.local_user)

        result = find_mentions(self.local_user, "@nutria hello")
        self.assertEqual(result, {})

    def test_find_mentions_unknown_remote(self, *_):
        """mention a user that isn't in the database"""
        with patch("bookwyrm.views.status.handle_remote_webfinger") as rw:
            rw.return_value = self.another_user
            result = find_mentions(self.local_user, "@beep@beep.com")
            self.assertEqual(result["@nutria"], self.another_user)
            self.assertEqual(result[f"@nutria@{DOMAIN}"], self.another_user)

        with patch("bookwyrm.views.status.handle_remote_webfinger") as rw:
            rw.return_value = None
            result = find_mentions(self.local_user, "@beep@beep.com")
            self.assertEqual(result, {})

    def test_create_status_hashtags(self, *_):
        """#mention a hashtag in a post"""
        view = views.CreateStatus.as_view()
        form = forms.CommentForm(
            {
                "content": "this is an #EXISTING hashtag but all uppercase, "
                + "this one is #NewTag.",
                "user": self.local_user.id,
                "book": self.book.id,
                "privacy": "public",
            }
        )
        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request, "comment")
        status = models.Status.objects.get()

        hashtags = models.Hashtag.objects.all()
        self.assertEqual(len(hashtags), 2)
        self.assertEqual(list(status.mention_hashtags.all()), list(hashtags))

        hashtag_existing = models.Hashtag.objects.filter(name="#existing").first()
        hashtag_new = models.Hashtag.objects.filter(name="#NewTag").first()
        self.assertEqual(
            status.content,
            "<p>this is an "
            + f'<a href="{hashtag_existing.remote_id}" data-mention="hashtag">'
            + "#EXISTING</a> hashtag but all uppercase, this one is "
            + f'<a href="{hashtag_new.remote_id}" data-mention="hashtag">'
            + "#NewTag</a>.</p>",
        )

    def test_find_or_create_hashtags(self, *_):
        """detect and look up #hashtags"""
        result = find_or_create_hashtags("no hashtag to be found here")
        self.assertEqual(result, {})

        result = find_or_create_hashtags("#existing")
        self.assertEqual(result["#existing"], self.existing_hashtag)

        result = find_or_create_hashtags("leading text #existing")
        self.assertEqual(result["#existing"], self.existing_hashtag)

        result = find_or_create_hashtags("leading #existing trailing")
        self.assertEqual(result["#existing"], self.existing_hashtag)

        self.assertIsNone(models.Hashtag.objects.filter(name="new").first())
        result = find_or_create_hashtags("leading #new trailing")
        new_hashtag = models.Hashtag.objects.filter(name="#new").first()
        self.assertIsNotNone(new_hashtag)
        self.assertEqual(result["#new"], new_hashtag)

        result = find_or_create_hashtags("leading #existing #new trailing")
        self.assertEqual(result["#existing"], self.existing_hashtag)
        self.assertEqual(result["#new"], new_hashtag)

        result = find_or_create_hashtags("#Braunbär")
        hashtag = models.Hashtag.objects.filter(name="#Braunbär").first()
        self.assertEqual(result["#Braunbär"], hashtag)

        result = find_or_create_hashtags("#ひぐま")
        hashtag = models.Hashtag.objects.filter(name="#ひぐま").first()
        self.assertEqual(result["#ひぐま"], hashtag)

    def test_format_links_simple_url(self, *_):
        """find and format urls into a tags"""
        url = "http://www.fish.com/"
        self.assertEqual(
            views.status.format_links(url), f'<a href="{url}">www.fish.com/</a>'
        )
        self.assertEqual(
            views.status.format_links(f"({url})"),
            f'(<a href="{url}">www.fish.com/</a>)',
        )

    def test_format_links_paragraph_break(self, *_):
        """find and format urls into a tags"""
        url = """okay

http://www.fish.com/"""
        self.assertEqual(
            views.status.format_links(url),
            'okay\n\n<a href="http://www.fish.com/">www.fish.com/</a>',
        )

    def test_format_links_parens(self, *_):
        """find and format urls into a tags"""
        url = "http://www.fish.com/"
        self.assertEqual(
            views.status.format_links(f"({url})"),
            f'(<a href="{url}">www.fish.com/</a>)',
        )

    def test_format_links_punctuation(self, *_):
        """don’t take trailing punctuation into account pls"""
        url = "http://www.fish.com/"
        self.assertEqual(
            views.status.format_links(f"{url}."),
            f'<a href="{url}">www.fish.com/</a>.',
        )

    def test_format_links_special_chars(self, *_):
        """find and format urls into a tags"""
        url = "https://archive.org/details/dli.granth.72113/page/n25/mode/2up"
        self.assertEqual(
            views.status.format_links(url),
            f'<a href="{url}">'
            "archive.org/details/dli.granth.72113/page/n25/mode/2up</a>",
        )
        url = "https://openlibrary.org/search?q=arkady+strugatsky&mode=everything"
        self.assertEqual(
            views.status.format_links(url),
            f'<a href="{url}">openlibrary.org/search'
            "?q=arkady+strugatsky&mode=everything</a>",
        )
        url = "https://tech.lgbt/@bookwyrm"
        self.assertEqual(
            views.status.format_links(url), f'<a href="{url}">tech.lgbt/@bookwyrm</a>'
        )
        url = "https://users.speakeasy.net/~lion/nb/book.pdf"
        self.assertEqual(
            views.status.format_links(url),
            f'<a href="{url}">users.speakeasy.net/~lion/nb/book.pdf</a>',
        )
        url = "https://pkm.one/#/page/The%20Book%20launched%20a%201000%20Note%20apps"
        self.assertEqual(
            views.status.format_links(url), f'<a href="{url}">{url[8:]}</a>'
        )

    def test_format_mentions_with_at_symbol_links(self, *_):
        """A link with an @username shouldn't treat the username as a mention"""
        content = "a link to https://example.com/user/@mouse"
        mentions = views.status.find_mentions(self.local_user, content)
        self.assertEqual(
            views.status.format_mentions(content, mentions),
            "a link to https://example.com/user/@mouse",
        )

    def test_format_hashtag_with_pound_symbol_links(self, *_):
        """A link with an @username shouldn't treat the username as a mention"""
        content = "a link to https://example.com/page#anchor"
        hashtags = views.status.find_or_create_hashtags(content)
        self.assertEqual(
            views.status.format_hashtags(content, hashtags),
            "a link to https://example.com/page#anchor",
        )

    def test_to_markdown(self, *_):
        """this is mostly handled in other places, but nonetheless"""
        text = "_hi_ and http://fish.com is <marquee>rad</marquee>"
        result = views.status.to_markdown(text)
        self.assertEqual(
            result,
            '<p><em>hi</em> and <a href="http://fish.com">fish.com</a> is rad</p>',
        )

    def test_to_markdown_detect_url(self, *_):
        """this is mostly handled in other places, but nonetheless"""
        text = "http://fish.com/@hello#okay"
        result = views.status.to_markdown(text)
        self.assertEqual(
            result,
            '<p><a href="http://fish.com/@hello#okay">fish.com/@hello#okay</a></p>',
        )

    def test_to_markdown_link(self, *_):
        """this is mostly handled in other places, but nonetheless"""
        text = "[hi](http://fish.com) is <marquee>rad</marquee>"
        result = views.status.to_markdown(text)
        self.assertEqual(result, '<p><a href="http://fish.com">hi</a> is rad</p>')

    def test_delete_status(self, mock, *_):
        """marks a status as deleted"""
        view = views.DeleteStatus.as_view()
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Status.objects.create(user=self.local_user, content="hi")
        self.assertFalse(status.deleted)
        request = self.factory.post("")
        request.user = self.local_user

        with patch("bookwyrm.activitystreams.remove_status_task.delay") as redis_mock:
            view(request, status.id)
            self.assertTrue(redis_mock.called)
        activity = json.loads(mock.call_args_list[1][1]["args"][1])
        self.assertEqual(activity["type"], "Delete")
        self.assertEqual(activity["object"]["type"], "Tombstone")
        status.refresh_from_db()
        self.assertTrue(status.deleted)

    def test_delete_status_permission_denied(self, *_):
        """marks a status as deleted"""
        view = views.DeleteStatus.as_view()
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Status.objects.create(user=self.local_user, content="hi")
        self.assertFalse(status.deleted)
        request = self.factory.post("")
        request.user = self.remote_user

        with self.assertRaises(PermissionDenied):
            view(request, status.id)

        status.refresh_from_db()
        self.assertFalse(status.deleted)

    def test_delete_status_moderator(self, mock, *_):
        """marks a status as deleted"""
        view = views.DeleteStatus.as_view()
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Status.objects.create(user=self.local_user, content="hi")
        self.assertFalse(status.deleted)
        request = self.factory.post("")
        request.user = self.remote_user
        request.user.is_superuser = True

        with patch("bookwyrm.activitystreams.remove_status_task.delay") as redis_mock:
            view(request, status.id)
            self.assertTrue(redis_mock.called)
        activity = json.loads(mock.call_args_list[1][1]["args"][1])
        self.assertEqual(activity["type"], "Delete")
        self.assertEqual(activity["object"]["type"], "Tombstone")
        status.refresh_from_db()
        self.assertTrue(status.deleted)

    def test_edit_status_get(self, *_):
        """load the edit status view"""
        view = views.EditStatus.as_view()
        status = models.Comment.objects.create(
            content="status", user=self.local_user, book=self.book
        )

        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, status.id)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_edit_status_get_reply(self, *_):
        """load the edit status view"""
        view = views.EditStatus.as_view()
        parent = models.Comment.objects.create(
            content="parent status", user=self.local_user, book=self.book
        )
        status = models.Status.objects.create(
            content="reply", user=self.local_user, reply_parent=parent
        )

        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, status.id)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_edit_status_success(self, mock, *_):
        """update an existing status"""
        status = models.Status.objects.create(content="status", user=self.local_user)
        self.assertIsNone(status.edited_date)
        view = views.CreateStatus.as_view()
        form = forms.CommentForm(
            {
                "content": "hi",
                "user": self.local_user.id,
                "book": self.book.id,
                "privacy": "public",
            }
        )
        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request, "comment", existing_status_id=status.id)
        activity = json.loads(mock.call_args_list[1][1]["args"][1])
        self.assertEqual(activity["type"], "Update")
        self.assertEqual(activity["object"]["id"], status.remote_id)

        status.refresh_from_db()
        self.assertEqual(status.content, "<p>hi</p>")
        self.assertIsNotNone(status.edited_date)

    def test_edit_status_permission_denied(self, *_):
        """update an existing status"""
        status = models.Status.objects.create(content="status", user=self.local_user)
        view = views.CreateStatus.as_view()
        form = forms.CommentForm(
            {
                "content": "hi",
                "user": self.local_user.id,
                "book": self.book.id,
                "privacy": "public",
            }
        )
        request = self.factory.post("", form.data)
        request.user = self.remote_user

        with self.assertRaises(PermissionDenied):
            view(request, "comment", existing_status_id=status.id)
