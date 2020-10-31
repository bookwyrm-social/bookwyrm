''' handles all the activity coming out of the server '''
from datetime import datetime

from django.db import IntegrityError, transaction
from django.http import HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests

from bookwyrm import activitypub
from bookwyrm import models
from bookwyrm.broadcast import broadcast
from bookwyrm.status import create_tag, create_notification
from bookwyrm.status import create_generated_note
from bookwyrm.status import delete_status
from bookwyrm.remote_user import get_or_create_remote_user


@csrf_exempt
def outbox(request, username):
    ''' outbox for the requested user '''
    if request.method != 'GET':
        return HttpResponseNotFound()

    try:
        user = models.User.objects.get(localname=username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    # collection overview
    return JsonResponse(
        user.to_outbox(**request.GET),
        encoder=activitypub.ActivityEncoder
    )


def handle_remote_webfinger(query):
    ''' webfingerin' other servers '''
    user = None
    domain = query.split('@')[1]
    try:
        user = models.User.objects.get(username=query)
    except models.User.DoesNotExist:
        url = 'https://%s/.well-known/webfinger?resource=acct:%s' % \
            (domain, query)
        try:
            response = requests.get(url)
        except requests.exceptions.ConnectionError:
            return None
        if not response.ok:
            return None
        data = response.json()
        for link in data['links']:
            if link['rel'] == 'self':
                try:
                    user = get_or_create_remote_user(link['href'])
                except KeyError:
                    return None
    return [user]


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


def handle_shelve(user, book, shelf):
    ''' a local user is getting a book put on their shelf '''
    # update the database
    shelve = models.ShelfBook(book=book, shelf=shelf, added_by=user)
    shelve.save()

    broadcast(user, shelve.to_add_activity(user))

    # tell the world about this cool thing that happened
    try:
        message = {
            'to-read': 'wants to read',
            'reading': 'started reading',
            'read': 'finished reading'
        }[shelf.identifier]
    except KeyError:
        # it's a non-standard shelf, don't worry about it
        return

    status = create_generated_note(user, message, mention_books=[book])
    status.save()

    if shelf.identifier == 'reading':
        read = models.ReadThrough(
            user=user,
            book=book,
            start_date=datetime.now())
        read.save()
    elif shelf.identifier == 'read':
        read = models.ReadThrough.objects.filter(
            user=user,
            book=book,
            finish_date=None).order_by('-created_date').first()
        if not read:
            read = models.ReadThrough(
                user=user,
                book=book,
                start_date=datetime.now())
        read.finish_date = datetime.now()
        read.save()

    broadcast(user, status.to_create_activity(user))


def handle_unshelve(user, book, shelf):
    ''' a local user is getting a book put on their shelf '''
    # update the database
    row = models.ShelfBook.objects.get(book=book, shelf=shelf)
    activity = row.to_remove_activity(user)
    row.delete()

    broadcast(user, activity)


def handle_imported_book(user, item, include_reviews, privacy):
    ''' process a goodreads csv and then post about it '''
    if isinstance(item.book, models.Work):
        item.book = item.book.default_edition
    if not item.book:
        return

    if item.shelf:
        desired_shelf = models.Shelf.objects.get(
            identifier=item.shelf,
            user=user
        )
        # shelve the book if it hasn't been shelved already
        shelf_book, created = models.ShelfBook.objects.get_or_create(
            book=item.book, shelf=desired_shelf, added_by=user)
        if created:
            broadcast(user, shelf_book.to_add_activity(user), privacy=privacy)

            # only add new read-throughs if the item isn't already shelved
            for read in item.reads:
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


def handle_delete_status(user, status):
    ''' delete a status and broadcast deletion to other servers '''
    delete_status(status)
    broadcast(user, status.to_delete_activity(user))


def handle_status(user, form):
    ''' generic handler for statuses '''
    status = form.save()

    # notify reply parent or (TODO) tagged users
    if status.reply_parent and status.reply_parent.user.local:
        create_notification(
            status.reply_parent.user,
            'REPLY',
            related_user=user,
            related_status=status
        )

    broadcast(user, status.to_create_activity(user), software='bookwyrm')

    # re-format the activity for non-bookwyrm servers
    if hasattr(status, 'pure_activity_serializer'):
        remote_activity = status.to_create_activity(user, pure=True)
        broadcast(user, remote_activity, software='other')


def handle_tag(user, book, name):
    ''' tag a book '''
    tag = create_tag(user, book, name)
    broadcast(user, tag.to_add_activity(user))


def handle_untag(user, book, name):
    ''' tag a book '''
    book = models.Book.objects.get(id=book)
    tag = models.Tag.objects.get(name=name, book=book, user=user)
    tag_activity = tag.to_remove_activity(user)
    tag.delete()

    broadcast(user, tag_activity)


def handle_favorite(user, status):
    ''' a user likes a status '''
    try:
        favorite = models.Favorite.objects.create(
            status=status,
            user=user
        )
    except IntegrityError:
        # you already fav'ed that
        return

    fav_activity = favorite.to_activity()
    broadcast(
        user, fav_activity, privacy='direct', direct_recipients=[status.user])


def handle_unfavorite(user, status):
    ''' a user likes a status '''
    try:
        favorite = models.Favorite.objects.get(
            status=status,
            user=user
        )
    except models.Favorite.DoesNotExist:
        # can't find that status, idk
        return

    fav_activity = activitypub.Undo(actor=user, object=favorite)
    broadcast(user, fav_activity, direct_recipients=[status.user])


def handle_boost(user, status):
    ''' a user wishes to boost a status '''
    if models.Boost.objects.filter(
            boosted_status=status, user=user).exists():
        # you already boosted that.
        return
    boost = models.Boost.objects.create(
        boosted_status=status,
        user=user,
    )
    boost.save()

    boost_activity = boost.to_activity()
    broadcast(user, boost_activity)


def handle_update_book(user, book):
    ''' broadcast the news about our book '''
    broadcast(user, book.to_update_activity(user))


def handle_update_user(user):
    ''' broadcast editing a user's profile '''
    broadcast(user, user.to_update_activity(user))
