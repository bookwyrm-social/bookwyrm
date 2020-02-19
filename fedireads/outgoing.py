''' handles all the activity coming out of the server '''
from django.http import HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
from urllib.parse import urlencode

from fedireads import activitypub
from fedireads import models
from fedireads.status import create_review, create_status
from fedireads.remote_user import get_or_create_remote_user
from fedireads.broadcast import get_recipients, broadcast


@csrf_exempt
def outbox(request, username):
    ''' outbox for the requested user '''
    user = models.User.objects.get(localname=username)
    if request.method != 'GET':
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
        ).all()[:limit]

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
                user = get_or_create_remote_user(link['href'])
    return user


def handle_outgoing_follow(user, to_follow):
    ''' someone local wants to follow someone '''
    activity = activitypub.get_follow_request(user, to_follow)
    errors = broadcast(user, activity, [to_follow.inbox])
    for error in errors:
        raise(error['error'])


def handle_outgoing_unfollow(user, to_unfollow):
    ''' someone local wants to follow someone '''
    relationship = models.UserRelationship.objects.get(
        user_object=user,
        user_subject=to_unfollow
    )
    activity = activitypub.get_unfollow(relationship)
    errors = broadcast(user, activity, [to_unfollow.inbox])
    to_unfollow.followers.remove(user)
    for error in errors:
        raise(error['error'])


def handle_outgoing_accept(user, to_follow, request_activity):
    ''' send an acceptance message to a follow request '''
    relationship = models.UserRelationship.objects.get(
        relationship_id=request_activity['id']
    )
    relationship.status = 'follow'
    relationship.save()
    activity = activitypub.get_accept(to_follow, request_activity)
    recipient = get_recipients(to_follow, 'direct', direct_recipients=[user])
    broadcast(to_follow, activity, recipient)


def handle_shelve(user, book, shelf):
    ''' a local user is getting a book put on their shelf '''
    # update the database
    # TODO: this should probably happen in incoming instead
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
    name = user.name if user.name else user.localname
    message = '%s %s %s' % (name, verb, book.data['title'])
    status = create_status(user, message, mention_books=[book])

    activity = activitypub.get_status(status)
    create_activity = activitypub.get_create(user, activity)

    broadcast(user, create_activity, recipients)


def handle_unshelve(user, book, shelf):
    ''' a local user is getting a book put on their shelf '''
    # update the database
    # TODO: this should probably happen in incoming instead
    row = models.ShelfBook.objects.get(book=book, shelf=shelf)
    row.delete()

    activity = activitypub.get_remove(user, book, shelf)
    recipients = get_recipients(user, 'public')

    broadcast(user, activity, recipients)


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


def handle_comment(user, review, content):
    ''' post a review '''
    # validated and saves the comment in the database so it has an id
    comment = create_status(user, content, reply_parent=review)
    comment_activity = activitypub.get_status(comment)
    create_activity = activitypub.get_create(user, comment_activity)

    recipients = get_recipients(user, 'public')
    broadcast(user, create_activity, recipients)

