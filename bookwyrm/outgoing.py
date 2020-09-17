''' handles all the activity coming out of the server '''
from datetime import datetime

from django.db import IntegrityError, transaction
from django.http import HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests

from fedireads import activitypub
from fedireads import models
from fedireads.broadcast import broadcast
from fedireads.status import create_review, create_status
from fedireads.status import create_quotation, create_comment
from fedireads.status import create_tag, create_notification, create_rating
from fedireads.remote_user import get_or_create_remote_user


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


def handle_account_search(query):
    ''' webfingerin' other servers '''
    user = None
    domain = query.split('@')[1]
    try:
        user = models.User.objects.get(username=query)
    except models.User.DoesNotExist:
        url = 'https://%s/.well-known/webfinger?resource=acct:%s' % \
            (domain, query)
        response = requests.get(url)
        if not response.ok:
            response.raise_for_status()
        data = response.json()
        for link in data['links']:
            if link['rel'] == 'self':
                try:
                    user = get_or_create_remote_user(link['href'])
                except KeyError:
                    return HttpResponseNotFound()
    return user


def handle_follow(user, to_follow):
    ''' someone local wants to follow someone '''
    try:
        relationship, _ = models.UserFollowRequest.objects.get_or_create(
            user_subject=user,
            user_object=to_follow,
        )
    except IntegrityError as err:
        if err.__cause__.diag.constraint_name != 'userfollowrequest_unique':
            raise
    activity = relationship.to_activity()
    broadcast(user, activity, direct_recipients=[to_follow])


def handle_unfollow(user, to_unfollow):
    ''' someone local wants to follow someone '''
    relationship = models.UserFollows.objects.get(
        user_subject=user,
        user_object=to_unfollow
    )
    activity = relationship.to_undo_activity(user)
    broadcast(user, activity, direct_recipients=[to_unfollow])
    to_unfollow.followers.remove(user)


def handle_accept(user, to_follow, follow_request):
    ''' send an acceptance message to a follow request '''
    with transaction.atomic():
        relationship = models.UserFollows.from_request(follow_request)
        follow_request.delete()
        relationship.save()

    activity = relationship.to_accept_activity()
    broadcast(to_follow, activity, privacy='direct', direct_recipients=[user])


def handle_reject(user, to_follow, relationship):
    ''' a local user who managed follows rejects a follow request '''
    activity = relationship.to_reject_activity(user)
    relationship.delete()
    broadcast(to_follow, activity, privacy='direct', direct_recipients=[user])


def handle_shelve(user, book, shelf):
    ''' a local user is getting a book put on their shelf '''
    # update the database
    shelve = models.ShelfBook(book=book, shelf=shelf, added_by=user).save()

    broadcast(user, shelve.to_add_activity(user))

    # tell the world about this cool thing that happened
    verb = {
        'to-read': 'wants to read',
        'reading': 'started reading',
        'read': 'finished reading'
    }[shelf.identifier]
    message = '%s "%s"' % (verb, book.title)
    status = create_status(user, message, mention_books=[book])
    status.status_type = 'Update'
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


def handle_import_books(user, items):
    ''' process a goodreads csv and then post about it '''
    new_books = []
    for item in items:
        if item.shelf:
            desired_shelf = models.Shelf.objects.get(
                identifier=item.shelf,
                user=user
            )
            if isinstance(item.book, models.Work):
                item.book = item.book.default_edition
            if not item.book:
                continue
            shelf_book, created = models.ShelfBook.objects.get_or_create(
                book=item.book, shelf=desired_shelf, added_by=user)
            if created:
                new_books.append(item.book)
                activity = shelf_book.to_add_activity(user)
                broadcast(user, activity)

                if item.rating or item.review:
                    review_title = "Review of {!r} on Goodreads".format(
                        item.book.title,
                    ) if item.review else ""
                    handle_review(
                        user,
                        item.book,
                        review_title,
                        item.review,
                        item.rating,
                    )
                for read in item.reads:
                    read.book = item.book
                    read.user = user
                    read.save()

    if new_books:
        message = 'imported {} books'.format(len(new_books))
        status = create_status(user, message, mention_books=new_books)
        status.status_type = 'Update'
        status.save()

        broadcast(user, status.to_create_activity(user))
        return status
    return None


def handle_rate(user, book, rating):
    ''' a review that's just a rating '''
    builder = create_rating
    handle_status(user, book, builder, rating)


def handle_review(user, book, name, content, rating):
    ''' post a review '''
    # validated and saves the review in the database so it has an id
    builder = create_review
    handle_status(user, book, builder, name, content, rating)


def handle_quotation(user, book, content, quote):
    ''' post a review '''
    # validated and saves the review in the database so it has an id
    builder = create_quotation
    handle_status(user, book, builder, content, quote)


def handle_comment(user, book, content):
    ''' post a comment '''
    # validated and saves the review in the database so it has an id
    builder = create_comment
    handle_status(user, book, builder, content)


def handle_status(user, book_id, builder, *args):
    ''' generic handler for statuses '''
    book = models.Edition.objects.get(id=book_id)
    status = builder(user, book, *args)

    broadcast(user, status.to_create_activity(user), software='fedireads')

    # re-format the activity for non-fedireads servers
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


def handle_reply(user, review, content):
    ''' respond to a review or status '''
    # validated and saves the comment in the database so it has an id
    reply = create_status(user, content, reply_parent=review)
    if reply.reply_parent:
        create_notification(
            reply.reply_parent.user,
            'REPLY',
            related_user=user,
            related_status=reply,
        )

    broadcast(user, reply.to_create_activity(user))


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
    broadcast(user, user.to_update_activity())
