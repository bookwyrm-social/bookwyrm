''' handles all the activity coming out of the server '''
from datetime import datetime
from urllib.parse import urlencode

from django.db import IntegrityError, transaction
from django.http import HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests

from fedireads import activitypub
from fedireads import models
from fedireads.broadcast import get_recipients, broadcast
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

    # paginated list of messages
    if request.GET.get('page'):
        limit = 20
        min_id = request.GET.get('min_id')
        max_id = request.GET.get('max_id')

        # filters for use in the django queryset min/max
        filters = {}
        # params for the outbox page id
        params = {'page': 'true'}
        if min_id != None:
            params['min_id'] = min_id
            filters['id__gt'] = min_id
        if max_id != None:
            params['max_id'] = max_id
            filters['id__lte'] = max_id

        page_id = user.outbox + '?' + urlencode(params)
        statuses = models.Status.objects.filter(
            user=user,
            **filters
        ).select_subclasses().all()[:limit]

        return JsonResponse(
            activitypub.get_outbox_page(user, page_id, statuses, max_id, min_id)
        )

    # collection overview
    size = models.Status.objects.filter(user=user).count()
    return JsonResponse(activitypub.get_outbox(user, size))


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
    activity = activitypub.get_follow_request(user, to_follow)
    broadcast(user, activity, [to_follow.inbox])


def handle_unfollow(user, to_unfollow):
    ''' someone local wants to follow someone '''
    relationship = models.UserFollows.objects.get(
        user_subject=user,
        user_object=to_unfollow
    )
    activity = activitypub.get_unfollow(relationship)
    broadcast(user, activity, [to_unfollow.inbox])
    to_unfollow.followers.remove(user)


def handle_accept(user, to_follow, follow_request):
    ''' send an acceptance message to a follow request '''
    with transaction.atomic():
        relationship = models.UserFollows.from_request(follow_request)
        follow_request.delete()
        relationship.save()

    activity = activitypub.get_accept(to_follow, follow_request)
    recipient = get_recipients(to_follow, 'direct', direct_recipients=[user])
    broadcast(to_follow, activity, recipient)


def handle_reject(user, to_follow, relationship):
    ''' a local user who managed follows rejects a follow request '''
    relationship.delete()

    activity = activitypub.get_reject(to_follow, relationship)
    recipient = get_recipients(to_follow, 'direct', direct_recipients=[user])
    broadcast(to_follow, activity, recipient)


def handle_shelve(user, book, shelf):
    ''' a local user is getting a book put on their shelf '''
    # update the database
    models.ShelfBook(book=book, shelf=shelf, added_by=user).save()

    activity = activitypub.get_add(user, book, shelf)
    recipients = get_recipients(user, 'public')
    broadcast(user, activity, recipients)

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

    activity = activitypub.get_status(status)
    create_activity = activitypub.get_create(user, activity)

    broadcast(user, create_activity, recipients)


def handle_unshelve(user, book, shelf):
    ''' a local user is getting a book put on their shelf '''
    # update the database
    row = models.ShelfBook.objects.get(book=book, shelf=shelf)
    row.delete()

    activity = activitypub.get_remove(user, book, shelf)
    recipients = get_recipients(user, 'public')

    broadcast(user, activity, recipients)


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
            _, created = models.ShelfBook.objects.get_or_create(
                book=item.book, shelf=desired_shelf, added_by=user)
            if created:
                new_books.append(item.book)
                activity = activitypub.get_add(user, item.book, desired_shelf)
                recipients = get_recipients(user, 'public')
                broadcast(user, activity, recipients)

                for read in item.reads:
                    read.book = item.book
                    read.user = user
                    read.save()

    if new_books:
        message = 'imported {} books'.format(len(new_books))
        status = create_status(user, message, mention_books=new_books)
        status.status_type = 'Update'
        status.save()

        create_activity = activitypub.get_create(
            user, activitypub.get_status(status))
        recipients = get_recipients(user, 'public')
        broadcast(user, create_activity, recipients)


def handle_rate(user, book, rating):
    ''' a review that's just a rating '''
    builder = create_rating
    local_serializer = activitypub.get_rating
    remote_serializer = activitypub.get_rating_note

    handle_status(
        user, book,
        builder, local_serializer, remote_serializer,
        rating
    )


def handle_review(user, book, name, content, rating):
    ''' post a review '''
    # validated and saves the review in the database so it has an id
    builder = create_review
    local_serializer = activitypub.get_review
    remote_serializer = activitypub.get_review_article
    handle_status(
        user, book, builder, local_serializer, remote_serializer,
        name, content, rating)


def handle_quotation(user, book, content, quote):
    ''' post a review '''
    # validated and saves the review in the database so it has an id
    builder = create_quotation
    local_serializer = activitypub.get_quotation
    remote_serializer = activitypub.get_quotation_article
    handle_status(
        user, book, builder, local_serializer, remote_serializer,
        content, quote)


def handle_comment(user, book, content):
    ''' post a review '''
    # validated and saves the review in the database so it has an id
    builder = create_comment
    local_serializer = activitypub.get_comment
    remote_serializer = activitypub.get_comment_article
    handle_status(
        user, book, builder, local_serializer, remote_serializer, content)


def handle_status(user, book, \
        builder, local_serializer, remote_serializer, *args):
    ''' generic handler for statuses '''
    status = builder(user, book, *args)

    activity = local_serializer(status)
    create_activity = activitypub.get_create(user, activity)
    local_recipients = get_recipients(user, 'public', limit='fedireads')
    broadcast(user, create_activity, local_recipients)

    # re-format the activity for non-fedireads servers
    remote_activity = remote_serializer(status)
    remote_create_activity = activitypub.get_create(user, remote_activity)

    remote_recipients = get_recipients(user, 'public', limit='other')
    broadcast(user, remote_create_activity, remote_recipients)


def handle_tag(user, book, name):
    ''' tag a book '''
    tag = create_tag(user, book, name)
    tag_activity = activitypub.get_add_tag(tag)

    recipients = get_recipients(user, 'public')
    broadcast(user, tag_activity, recipients)


def handle_untag(user, book, name):
    ''' tag a book '''
    book = models.Book.objects.get(fedireads_key=book)
    tag = models.Tag.objects.get(name=name, book=book, user=user)
    tag_activity = activitypub.get_remove_tag(tag)
    tag.delete()

    recipients = get_recipients(user, 'public')
    broadcast(user, tag_activity, recipients)


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
    reply_activity = activitypub.get_status(reply)
    create_activity = activitypub.get_create(user, reply_activity)

    recipients = get_recipients(user, 'public')
    broadcast(user, create_activity, recipients)


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

    fav_activity = activitypub.get_favorite(favorite)
    recipients = get_recipients(user, 'direct', [status.user])
    broadcast(user, fav_activity, recipients)


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

    fav_activity = activitypub.get_unfavorite(favorite)
    recipients = get_recipients(user, 'direct', [status.user])
    broadcast(user, fav_activity, recipients)

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

    boost_activity = activitypub.get_boost(boost)
    recipients = get_recipients(user, 'public')
    broadcast(user, boost_activity, recipients)

def handle_update_book(user, book):
    ''' broadcast the news about our book '''
    book_activity = activitypub.get_book(book)
    update_activity = activitypub.get_update(user, book_activity)
    recipients = get_recipients(None, 'public')
    broadcast(user, update_activity, recipients)


def handle_update_user(user):
    ''' broadcast editing a user's profile '''
    actor = activitypub.get_actor(user)
    update_activity = activitypub.get_update(user, actor)
    recipients = get_recipients(user, 'public')
    broadcast(user, update_activity, recipients)

