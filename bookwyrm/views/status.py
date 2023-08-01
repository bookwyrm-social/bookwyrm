""" what are we here for if not for posting """
import re
import logging
from urllib.parse import urlparse

from django.contrib.auth.decorators import login_required
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from markdown import markdown
from bookwyrm import forms, models
from bookwyrm.utils import regex, sanitizer
from .helpers import handle_remote_webfinger, is_api_request
from .helpers import load_date_in_user_tz_as_utc, redirect_to_referer

logger = logging.getLogger(__name__)


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class EditStatus(View):
    """the view for *posting*"""

    def get(self, request, status_id):  # pylint: disable=unused-argument
        """load the edit panel"""
        status = get_object_or_404(
            models.Status.objects.select_subclasses(), id=status_id
        )

        status_type = "reply" if status.reply_parent else status.status_type.lower()
        data = {
            "type": status_type,
            "book": getattr(status, "book", None),
            "draft": status,
        }
        return TemplateResponse(request, "compose.html", data)


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class CreateStatus(View):
    """the view for *posting*"""

    def get(self, request, status_type):  # pylint: disable=unused-argument
        """compose view (...not used?)"""
        book = get_object_or_404(models.Edition, id=request.GET.get("book"))
        data = {"book": book}
        return TemplateResponse(request, "compose.html", data)

    # pylint: disable=too-many-branches
    def post(self, request, status_type, existing_status_id=None):
        """create status of whatever type"""
        created = not existing_status_id
        existing_status = None
        if existing_status_id:
            existing_status = get_object_or_404(
                models.Status.objects.select_subclasses(), id=existing_status_id
            )
            existing_status.edited_date = timezone.now()

        status_type = status_type[0].upper() + status_type[1:]

        try:
            form = getattr(forms, f"{status_type}Form")(
                request.POST, instance=existing_status
            )
        except AttributeError as err:
            logger.exception(err)
            return HttpResponseBadRequest()

        if not form.is_valid():
            if is_api_request(request):
                logger.exception(form.errors)
                return HttpResponseBadRequest()
            return redirect_to_referer(request)

        status = form.save(request, commit=False)
        status.ready = False
        # save the plain, unformatted version of the status for future editing
        status.raw_content = status.content
        if hasattr(status, "quote"):
            status.raw_quote = status.quote

        status.sensitive = status.content_warning not in [None, ""]
        # the status has to be saved now before we can add many to many fields
        # like mentions
        status.save(broadcast=False)

        # inspect the text for user tags
        content = status.content
        mentions = find_mentions(request.user, content)
        for (_, mention_user) in mentions.items():
            # add them to status mentions fk
            status.mention_users.add(mention_user)
        content = format_mentions(content, mentions)

        # add reply parent to mentions
        if status.reply_parent:
            status.mention_users.add(status.reply_parent.user)

        # inspect the text for hashtags
        hashtags = find_or_create_hashtags(content)
        for (_, mention_hashtag) in hashtags.items():
            # add them to status mentions fk
            status.mention_hashtags.add(mention_hashtag)
        content = format_hashtags(content, hashtags)

        # deduplicate mentions
        status.mention_users.set(set(status.mention_users.all()))

        # don't apply formatting to generated notes
        if not isinstance(status, models.GeneratedNote) and content:
            status.content = to_markdown(content)
        # do apply formatting to quotes
        if hasattr(status, "quote"):
            status.quote = to_markdown(status.quote)

        status.ready = True
        status.save(created=created)

        # update a readthrough, if needed
        if bool(request.POST.get("id")):
            try:
                edit_readthrough(request)
            except Http404:
                pass

        if is_api_request(request):
            return HttpResponse()
        return redirect_to_referer(request)


def format_mentions(content, mentions):
    """Detect @mentions and make them links"""
    for (mention_text, mention_user) in mentions.items():
        # turn the mention into a link
        content = re.sub(
            rf"(?<!/)\B{mention_text}\b(?!@)",
            rf'<a href="{mention_user.remote_id}">{mention_text}</a>',
            content,
        )
    return content


def format_hashtags(content, hashtags):
    """Detect #hashtags and make them links"""
    for (mention_text, mention_hashtag) in hashtags.items():
        # turn the mention into a link
        content = re.sub(
            rf"(?<!/)\B{mention_text}\b(?!@)",
            rf'<a href="{mention_hashtag.remote_id}" data-mention="hashtag">'
            + rf"{mention_text}</a>",
            content,
        )
    return content


@method_decorator(login_required, name="dispatch")
class DeleteStatus(View):
    """tombstone that bad boy"""

    def post(self, request, status_id):
        """delete and tombstone a status"""
        status = get_object_or_404(models.Status, id=status_id)

        # don't let people delete other people's statuses
        status.raise_not_deletable(request.user)

        # perform deletion
        status.delete()
        return redirect("/")


@login_required
@require_POST
def update_progress(request, book_id):  # pylint: disable=unused-argument
    """Either it's just a progress update, or it's a comment with a progress update"""
    if request.POST.get("post-status"):
        return CreateStatus.as_view()(request, "comment")
    return edit_readthrough(request)


@login_required
@require_POST
def edit_readthrough(request):
    """can't use the form because the dates are too finnicky"""
    # TODO: remove this, it duplicates the code in the ReadThrough view
    readthrough = get_object_or_404(models.ReadThrough, id=request.POST.get("id"))

    readthrough.start_date = load_date_in_user_tz_as_utc(
        request.POST.get("start_date"), request.user
    )
    readthrough.finish_date = load_date_in_user_tz_as_utc(
        request.POST.get("finish_date"), request.user
    )

    progress = request.POST.get("progress")
    try:
        progress = int(progress)
        readthrough.progress = progress
    except (ValueError, TypeError):
        pass

    progress_mode = request.POST.get("progress_mode")
    try:
        progress_mode = models.ProgressMode(progress_mode)
        readthrough.progress_mode = progress_mode
    except ValueError:
        pass

    readthrough.save()

    # record the progress update individually
    # use default now for date field
    readthrough.create_update()

    if is_api_request(request):
        return HttpResponse()
    return redirect_to_referer(request)


def find_mentions(user, content):
    """detect @mentions in raw status content"""
    if not content:
        return {}
    # The regex has nested match groups, so the 0th entry has the full (outer) match
    # And because the strict username starts with @, the username is 1st char onward
    usernames = [m[0][1:] for m in re.findall(regex.STRICT_USERNAME, content)]

    known_users = (
        models.User.viewer_aware_objects(user)
        .filter(Q(username__in=usernames) | Q(localname__in=usernames))
        .distinct()
    )
    # Prepare a lookup based on both username and localname
    username_dict = {
        **{f"@{u.username}": u for u in known_users},
        **{f"@{u.localname}": u for u in known_users.filter(local=True)},
    }

    # Users not captured here could be blocked or not yet loaded on the server
    not_found = set(usernames) - set(username_dict.keys())
    for username in not_found:
        mention_user = handle_remote_webfinger(username, unknown_only=True)
        if not mention_user:
            # this user is blocked or can't be found
            continue
        username_dict[f"@{mention_user.username}"] = mention_user
        username_dict[f"@{mention_user.localname}"] = mention_user
    return username_dict


def find_or_create_hashtags(content):
    """detect #hashtags in raw status content

    it stores hashtags case-sensitive, but ensures that an existing
    hashtag with different case are found and re-used. for example,
    an existing #BookWyrm hashtag will be found and used even if the
    status content is using #bookwyrm.
    """
    if not content:
        return {}

    found_hashtags = {t.lower(): t for t in re.findall(regex.HASHTAG, content)}
    if len(found_hashtags) == 0:
        return {}

    known_hashtags = {
        t.name.lower(): t
        for t in models.Hashtag.objects.filter(
            Q(name__in=found_hashtags.keys())
        ).distinct()
    }

    not_found = found_hashtags.keys() - known_hashtags.keys()
    for lower_name in not_found:
        tag_name = found_hashtags[lower_name]
        mention_hashtag = models.Hashtag(name=tag_name)
        mention_hashtag.save()
        known_hashtags[lower_name] = mention_hashtag

    return {found_hashtags[k]: v for k, v in known_hashtags.items()}


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

        ends_with_punctuation = _ends_with_punctuation(potential_link)
        if ends_with_punctuation:
            punctuation_glyph = potential_link[-1]
            potential_link = potential_link[0:-1]

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

            formatted_content += f'<a href="{potential_link}">{link}</a>'
        except (ValidationError, UnicodeError):
            formatted_content += potential_link

        if wrapped:
            formatted_content += wrapper_close

        if ends_with_punctuation:
            formatted_content += punctuation_glyph

    return formatted_content


def _wrapped(text):
    """check if a line of text is wrapped"""
    wrappers = [("(", ")"), ("[", "]"), ("{", "}")]
    for wrapper in wrappers:
        if text[0] == wrapper[0] and text[-1] == wrapper[-1]:
            return True
    return False


def _ends_with_punctuation(text):
    """check if a line of text ends with a punctuation glyph"""
    glyphs = [".", ",", ";", ":", "!", "?", "”", "’", '"', "»"]
    for glyph in glyphs:
        if text[-1] == glyph:
            return True
    return False


def to_markdown(content):
    """catch links and convert to markdown"""
    content = format_links(content)
    content = markdown(content)
    # sanitize resulting html
    return sanitizer.clean(content)
