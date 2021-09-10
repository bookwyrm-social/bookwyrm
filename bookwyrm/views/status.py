""" what are we here for if not for posting """
import re
from urllib.parse import urlparse

from django.contrib.auth.decorators import login_required
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from markdown import markdown
from bookwyrm import forms, models
from bookwyrm.sanitize_html import InputHtmlParser
from bookwyrm.settings import DOMAIN
from bookwyrm.utils import regex
from .helpers import handle_remote_webfinger, is_api_request
from .reading import edit_readthrough


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class CreateStatus(View):
    """the view for *posting*"""

    def get(self, request, status_type):  # pylint: disable=unused-argument
        """compose view (used for delete-and-redraft)"""
        book = get_object_or_404(models.Edition, id=request.GET.get("book"))
        data = {"book": book}
        return TemplateResponse(request, "compose.html", data)

    def post(self, request, status_type):
        """create  status of whatever type"""
        status_type = status_type[0].upper() + status_type[1:]

        try:
            form = getattr(forms, "%sForm" % status_type)(request.POST)
        except AttributeError:
            return HttpResponseBadRequest()
        if not form.is_valid():
            if is_api_request(request):
                return HttpResponse(status=500)
            return redirect(request.headers.get("Referer", "/"))

        status = form.save(commit=False)
        if not status.sensitive and status.content_warning:
            # the cw text field remains populated when you click "remove"
            status.content_warning = None
        status.save(broadcast=False)

        # inspect the text for user tags
        content = status.content
        for (mention_text, mention_user) in find_mentions(content):
            # add them to status mentions fk
            status.mention_users.add(mention_user)

            # turn the mention into a link
            content = re.sub(
                r"%s([^@]|$)" % mention_text,
                r'<a href="%s">%s</a>\g<1>' % (mention_user.remote_id, mention_text),
                content,
            )
        # add reply parent to mentions
        if status.reply_parent:
            status.mention_users.add(status.reply_parent.user)

        # deduplicate mentions
        status.mention_users.set(set(status.mention_users.all()))

        # don't apply formatting to generated notes
        if not isinstance(status, models.GeneratedNote) and content:
            status.content = to_markdown(content)
        # do apply formatting to quotes
        if hasattr(status, "quote"):
            status.quote = to_markdown(status.quote)

        status.save(created=True)

        # update a readthorugh, if needed
        edit_readthrough(request)

        if is_api_request(request):
            return HttpResponse()
        return redirect("/")


@method_decorator(login_required, name="dispatch")
class DeleteStatus(View):
    """tombstone that bad boy"""

    def post(self, request, status_id):
        """delete and tombstone a status"""
        status = get_object_or_404(models.Status, id=status_id)

        # don't let people delete other people's statuses
        if status.user != request.user and not request.user.has_perm("moderate_post"):
            return HttpResponseBadRequest()

        # perform deletion
        status.delete()
        return redirect(request.headers.get("Referer", "/"))


@method_decorator(login_required, name="dispatch")
class DeleteAndRedraft(View):
    """delete a status but let the user re-create it"""

    def post(self, request, status_id):
        """delete and tombstone a status"""
        status = get_object_or_404(
            models.Status.objects.select_subclasses(), id=status_id
        )
        if isinstance(status, (models.GeneratedNote, models.ReviewRating)):
            return HttpResponseBadRequest()

        # don't let people redraft other people's statuses
        if status.user != request.user:
            return HttpResponseBadRequest()

        status_type = status.status_type.lower()
        if status.reply_parent:
            status_type = "reply"

        data = {
            "draft": status,
            "type": status_type,
        }
        if hasattr(status, "book"):
            data["book"] = status.book
        elif status.mention_books:
            data["book"] = status.mention_books.first()

        # perform deletion
        status.delete()
        return TemplateResponse(request, "compose.html", data)


def find_mentions(content):
    """detect @mentions in raw status content"""
    if not content:
        return
    for match in re.finditer(regex.STRICT_USERNAME, content):
        username = match.group().strip().split("@")[1:]
        if len(username) == 1:
            # this looks like a local user (@user), fill in the domain
            username.append(DOMAIN)
        username = "@".join(username)

        mention_user = handle_remote_webfinger(username)
        if not mention_user:
            # we can ignore users we don't know about
            continue
        yield (match.group(), mention_user)


def format_links(content):
    """detect and format links"""
    validator = URLValidator()
    formatted_content = ""
    split_content = re.split(r"(\s+)", content)

    for potential_link in split_content:
        if not potential_link:
            continue
        wrapped = _wrapped(potential_link)
        if wrapped:
            wrapper_close = potential_link[-1]
            formatted_content += potential_link[0]
            potential_link = potential_link[1:-1]

        try:
            # raises an error on anything that's not a valid link
            validator(potential_link)

            # use everything but the scheme in the presentation of the link
            url = urlparse(potential_link)
            link = url.netloc + url.path + url.params
            if url.query != "":
                link += "?" + url.query
            if url.fragment != "":
                link += "#" + url.fragment

            formatted_content += '<a href="%s">%s</a>' % (potential_link, link)
        except (ValidationError, UnicodeError):
            formatted_content += potential_link

        if wrapped:
            formatted_content += wrapper_close

    return formatted_content


def _wrapped(text):
    """check if a line of text is wrapped"""
    wrappers = [("(", ")"), ("[", "]"), ("{", "}")]
    for wrapper in wrappers:
        if text[0] == wrapper[0] and text[-1] == wrapper[-1]:
            return True
    return False


def to_markdown(content):
    """catch links and convert to markdown"""
    content = format_links(content)
    content = markdown(content)
    # sanitize resulting html
    sanitizer = InputHtmlParser()
    sanitizer.feed(content)
    return sanitizer.get_output()
