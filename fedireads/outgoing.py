''' handles all the activity coming out of the server '''
from django.db import IntegrityError, transaction
from django.http import HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
from urllib.parse import urlencode

from fedireads import activitypub
from fedireads import models
from fedireads.status import create_review, create_status, create_tag, \
    create_notification, create_comment
from fedireads.remote_user import get_or_create_remote_user
from fedireads.broadcast import get_recipients, broadcast


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


def handle_outgoing_follow(user, to_follow):
    ''' someone local wants to follow someone '''
    activity = activitypub.get_follow_request(user, to_follow)
    errors = broadcast(user, activity, [to_follow.inbox])
    for error in errors:
        raise(error['error'])


def handle_outgoing_unfollow(user, to_unfollow):
    ''' someone local wants to follow someone '''
    relationship = models.UserFollows.objects.get(
        user_subject=user,
        user_object=to_unfollow
    )
    activity = activitypub.get_unfollow(relationship)
    errors = broadcast(user, activity, [to_unfollow.inbox])
    to_unfollow.followers.remove(user)
    for error in errors:
        raise(error['error'])


def handle_outgoing_accept(user, to_follow, follow_request):
    ''' send an acceptance message to a follow request '''
    with transaction.atomic():
        relationship = models.UserFollows.from_request(follow_request)
        follow_request.delete()
        relationship.save()

    activity = activitypub.get_accept(to_follow, follow_request)
    recipient = get_recipients(to_follow, 'direct', direct_recipients=[user])
    broadcast(to_follow, activity, recipient)

def handle_outgoing_reject(user, to_follow, relationship):
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
            _, created = models.ShelfBook.objects.get_or_create(
                book=item.book, shelf=desired_shelf, added_by=user)
            if created:
                new_books.append(item.book)
                activity = activitypub.get_add(user, item.book, desired_shelf)
                recipients = get_recipients(user, 'public')
                broadcast(user, activity, recipients)

    if new_books:
        message = 'imported {} books'.format(len(new_books))
        status = create_status(user, message, mention_books=new_books)
        status.status_type = 'Update'
        status.save()

        create_activity = activitypub.get_create(
            user, activitypub.get_status(status))
        broadcast(user, create_activity, get_recipients(user, 'public'))


def handle_review(user, book, name, content, rating):
    ''' post a review '''
    # validated and saves the review in the database so it has an id
    review = create_review(user, book, name, content, rating)

    review_activity = activitypub.get_review(review)
    review_create_activity = activitypub.get_create(user, review_activity)
    fr_recipients = get_recipients(user, 'public', limit='fedireads')
    broadcast(user, review_create_activity, fr_recipients)

    # re-format the activity for non-fedireads servers
    article_activity = activitypub.get_review_article(review)
    article_create_activity = activitypub.get_create(user, article_activity)

    other_recipients = get_recipients(user, 'public', limit='other')
    broadcast(user, article_create_activity, other_recipients)


def handle_comment(user, book, name, content):
    ''' post a review '''
    # validated and saves the review in the database so it has an id
    comment = create_comment(user, book, name, content)

    comment_activity = activitypub.get_comment(comment)
    comment_create_activity = activitypub.get_create(user, comment_activity)
    fr_recipients = get_recipients(user, 'public', limit='fedireads')
    broadcast(user, comment_create_activity, fr_recipients)

    # re-format the activity for non-fedireads servers
    article_activity = activitypub.get_comment_article(comment)
    article_create_activity = activitypub.get_create(user, article_activity)

    other_recipients = get_recipients(user, 'public', limit='other')
    broadcast(user, article_create_activity, other_recipients)


def handle_tag(user, book, name):
    ''' tag a book '''
    tag = create_tag(user, book, name)
    tag_activity = activitypub.get_add_tag(tag)

    recipients = get_recipients(user, 'public')
    broadcast(user, tag_activity, recipients)


def handle_untag(user, book, name):
    ''' tag a book '''
    book = models.Book.objects.get(local_key=book)
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


def handle_outgoing_favorite(user, status):
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


def handle_outgoing_unfavorite(user, status):
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

