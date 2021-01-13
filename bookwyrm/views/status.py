''' what are we here for if not for posting '''
import re
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from markdown import markdown

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.broadcast import broadcast
from bookwyrm.sanitize_html import InputHtmlParser
from bookwyrm.settings import DOMAIN
from bookwyrm.status import create_notification, delete_status
from bookwyrm.utils import regex
from .helpers import get_user_from_username, handle_remote_webfinger
from .helpers import is_api_request, is_bookworm_request, status_visible_to_user


# pylint: disable= no-self-use
class Status(View):
    ''' the view for *posting* '''
    def get(self, request, username, status_id):
        ''' display a particular status (and replies, etc) '''
        try:
            user = get_user_from_username(username)
            status = models.Status.objects.select_subclasses().get(id=status_id)
        except ValueError:
            return HttpResponseNotFound()

        # the url should have the poster's username in it
        if user != status.user:
            return HttpResponseNotFound()

        # make sure the user is authorized to see the status
        if not status_visible_to_user(request.user, status):
            return HttpResponseNotFound()

        if is_api_request(request):
            return ActivitypubResponse(
                status.to_activity(pure=not is_bookworm_request(request)))

        data = {
            'title': 'Status by %s' % user.username,
            'status': status,
        }
        return TemplateResponse(request, 'status.html', data)


@method_decorator(login_required, name='dispatch')
class CreateStatus(View):
    ''' get posting '''
    def post(self, request, status_type):
        ''' create  status of whatever type '''
        status_type = status_type[0].upper() + status_type[1:]
        try:
            form = getattr(forms, '%sForm' % status_type)(request.POST)
        except AttributeError:
            return HttpResponseBadRequest()
        if not form.is_valid():
            return redirect(request.headers.get('Referer', '/'))

        status = form.save(commit=False)
        if not status.sensitive and status.content_warning:
            # the cw text field remains populated when you click "remove"
            status.content_warning = None
        status.save()

        # inspect the text for user tags
        content = status.content
        for (mention_text, mention_user) in find_mentions(content):
            # add them to status mentions fk
            status.mention_users.add(mention_user)

            # turn the mention into a link
            content = re.sub(
                r'%s([^@]|$)' % mention_text,
                r'<a href="%s">%s</a>\g<1>' % \
                    (mention_user.remote_id, mention_text),
                content)

        # add reply parent to mentions and notify
        if status.reply_parent:
            status.mention_users.add(status.reply_parent.user)
            for mention_user in status.reply_parent.mention_users.all():
                status.mention_users.add(mention_user)

            if status.reply_parent.user.local:
                create_notification(
                    status.reply_parent.user,
                    'REPLY',
                    related_user=request.user,
                    related_status=status
                )

        # deduplicate mentions
        status.mention_users.set(set(status.mention_users.all()))
        # create mention notifications
        for mention_user in status.mention_users.all():
            if status.reply_parent and mention_user == status.reply_parent.user:
                continue
            if mention_user.local:
                create_notification(
                    mention_user,
                    'MENTION',
                    related_user=request.user,
                    related_status=status
                )

        # don't apply formatting to generated notes
        if not isinstance(status, models.GeneratedNote):
            status.content = to_markdown(content)
        # do apply formatting to quotes
        if hasattr(status, 'quote'):
            status.quote = to_markdown(status.quote)

        status.save()

        broadcast(
            request.user,
            status.to_create_activity(request.user),
            software='bookwyrm')

        # re-format the activity for non-bookwyrm servers
        remote_activity = status.to_create_activity(request.user, pure=True)
        broadcast(request.user, remote_activity, software='other')
        return redirect(request.headers.get('Referer', '/'))


class DeleteStatus(View):
    ''' tombstone that bad boy '''
    def post(self, request, status_id):
        ''' delete and tombstone a status '''
        status = get_object_or_404(models.Status, id=status_id)

        # don't let people delete other people's statuses
        if status.user != request.user:
            return HttpResponseBadRequest()

        # perform deletion
        delete_status(status)
        broadcast(request.user, status.to_delete_activity(request.user))
        return redirect(request.headers.get('Referer', '/'))


class Replies(View):
    ''' replies page (a json view of status) '''
    def get(self, request, username, status_id):
        ''' ordered collection of replies to a status '''
        # the html view is the same as Status
        if not is_api_request(request):
            status_view = Status.as_view()
            return status_view(request, username, status_id)

        # the json view is different than Status
        status = models.Status.objects.get(id=status_id)
        if status.user.localname != username:
            return HttpResponseNotFound()

        return ActivitypubResponse(status.to_replies(**request.GET))

def find_mentions(content):
    ''' detect @mentions in raw status content '''
    for match in re.finditer(regex.strict_username, content):
        username = match.group().strip().split('@')[1:]
        if len(username) == 1:
            # this looks like a local user (@user), fill in the domain
            username.append(DOMAIN)
        username = '@'.join(username)

        mention_user = handle_remote_webfinger(username)
        if not mention_user:
            # we can ignore users we don't know about
            continue
        yield (match.group(), mention_user)


def format_links(content):
    ''' detect and format links '''
    return re.sub(
        r'([^(href=")]|^|\()(https?:\/\/(%s([\w\.\-_\/+&\?=:;,])*))' % \
                regex.domain,
        r'\g<1><a href="\g<2>">\g<3></a>',
        content)

def to_markdown(content):
    ''' catch links and convert to markdown '''
    content = format_links(content)
    content = markdown(content)
    # sanitize resulting html
    sanitizer = InputHtmlParser()
    sanitizer.feed(content)
    return sanitizer.get_output()
