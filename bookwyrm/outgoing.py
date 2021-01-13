''' handles all the activity coming out of the server '''
import re

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from markdown import markdown
from requests import HTTPError

from bookwyrm import activitypub
from bookwyrm import models
from bookwyrm.connectors import get_data, ConnectorException
from bookwyrm.broadcast import broadcast
from bookwyrm.sanitize_html import InputHtmlParser
from bookwyrm.status import create_notification
from bookwyrm.status import create_generated_note
from bookwyrm.settings import DOMAIN
from bookwyrm.utils import regex


@csrf_exempt
@require_GET
def outbox(request, username):
    ''' outbox for the requested user '''
    user = get_object_or_404(models.User, localname=username)
    filter_type = request.GET.get('type')
    if filter_type not in models.status_models:
        filter_type = None

    return JsonResponse(
        user.to_outbox(**request.GET, filter_type=filter_type),
        encoder=activitypub.ActivityEncoder
    )


def handle_remote_webfinger(query):
    ''' webfingerin' other servers '''
    user = None

    # usernames could be @user@domain or user@domain
    if not query:
        return None

    if query[0] == '@':
        query = query[1:]

    try:
        domain = query.split('@')[1]
    except IndexError:
        return None

    try:
        user = models.User.objects.get(username=query)
    except models.User.DoesNotExist:
        url = 'https://%s/.well-known/webfinger?resource=acct:%s' % \
            (domain, query)
        try:
            data = get_data(url)
        except (ConnectorException, HTTPError):
            return None

        for link in data.get('links'):
            if link.get('rel') == 'self':
                try:
                    user = activitypub.resolve_remote_id(
                        models.User, link['href']
                    )
                except KeyError:
                    return None
    return user


def handle_follow(user, to_follow):
    ''' someone local wants to follow someone '''
    relationship, _ = models.UserFollowRequest.objects.get_or_create(
        user_subject=user,
        user_object=to_follow,
    )
    activity = relationship.to_activity()
    broadcast(user, activity, privacy='direct', direct_recipients=[to_follow])


def handle_unfollow(user, to_unfollow):
    ''' someone local wants to follow someone '''
    relationship = models.UserFollows.objects.get(
        user_subject=user,
        user_object=to_unfollow
    )
    activity = relationship.to_undo_activity(user)
    broadcast(user, activity, privacy='direct', direct_recipients=[to_unfollow])
    to_unfollow.followers.remove(user)


def handle_accept(follow_request):
    ''' send an acceptance message to a follow request '''
    user = follow_request.user_subject
    to_follow = follow_request.user_object
    with transaction.atomic():
        relationship = models.UserFollows.from_request(follow_request)
        follow_request.delete()
        relationship.save()

    activity = relationship.to_accept_activity()
    broadcast(to_follow, activity, privacy='direct', direct_recipients=[user])


def handle_reject(follow_request):
    ''' a local user who managed follows rejects a follow request '''
    user = follow_request.user_subject
    to_follow = follow_request.user_object
    activity = follow_request.to_reject_activity()
    follow_request.delete()
    broadcast(to_follow, activity, privacy='direct', direct_recipients=[user])


def handle_imported_book(user, item, include_reviews, privacy):
    ''' process a goodreads csv and then post about it '''
    if isinstance(item.book, models.Work):
        item.book = item.book.default_edition
    if not item.book:
        return

    existing_shelf = models.ShelfBook.objects.filter(
        book=item.book, added_by=user).exists()

    # shelve the book if it hasn't been shelved already
    if item.shelf and not existing_shelf:
        desired_shelf = models.Shelf.objects.get(
            identifier=item.shelf,
            user=user
        )
        shelf_book = models.ShelfBook.objects.create(
            book=item.book, shelf=desired_shelf, added_by=user)
        broadcast(user, shelf_book.to_add_activity(user), privacy=privacy)

    for read in item.reads:
        # check for an existing readthrough with the same dates
        if models.ReadThrough.objects.filter(
                user=user, book=item.book,
                start_date=read.start_date,
                finish_date=read.finish_date
            ).exists():
            continue
        read.book = item.book
        read.user = user
        read.save()

    if include_reviews and (item.rating or item.review):
        review_title = 'Review of {!r} on Goodreads'.format(
            item.book.title,
        ) if item.review else ''

        # we don't know the publication date of the review,
        # but "now" is a bad guess
        published_date_guess = item.date_read or item.date_added
        review = models.Review.objects.create(
            user=user,
            book=item.book,
            name=review_title,
            content=item.review,
            rating=item.rating,
            published_date=published_date_guess,
            privacy=privacy,
        )
        # we don't need to send out pure activities because non-bookwyrm
        # instances don't need this data
        broadcast(user, review.to_create_activity(user), privacy=privacy)
