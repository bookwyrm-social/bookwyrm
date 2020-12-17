''' template filters '''
from uuid import uuid4
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django import template
from django.utils import timezone

from bookwyrm import models


register = template.Library()

@register.filter(name='dict_key')
def dict_key(d, k):
    ''' Returns the given key from a dictionary. '''
    return d.get(k) or 0


@register.filter(name='rating')
def get_rating(book, user):
    ''' get a user's rating of a book '''
    rating = models.Review.objects.filter(
        user=user,
        book=book,
        rating__isnull=False,
    ).order_by('-published_date').first()
    if rating:
        return rating.rating
    return 0


@register.filter(name='username')
def get_user_identifier(user):
    ''' use localname for local users, username for remote '''
    return user.localname if user.localname else user.username


@register.filter(name='notification_count')
def get_notification_count(user):
    ''' how many UNREAD notifications are there '''
    return user.notification_set.filter(read=False).count()


@register.filter(name='replies')
def get_replies(status):
    ''' get all direct replies to a status '''
    #TODO: this limit could cause problems
    return models.Status.objects.filter(
        reply_parent=status,
        deleted=False,
    ).select_subclasses().all()[:10]


@register.filter(name='parent')
def get_parent(status):
    ''' get the reply parent for a status '''
    return models.Status.objects.filter(
        id=status.reply_parent_id
    ).select_subclasses().get()


@register.filter(name='liked')
def get_user_liked(user, status):
    ''' did the given user fav a status? '''
    try:
        models.Favorite.objects.get(user=user, status=status)
        return True
    except models.Favorite.DoesNotExist:
        return False


@register.filter(name='boosted')
def get_user_boosted(user, status):
    ''' did the given user fav a status? '''
    return user.id in status.boosters.all().values_list('user', flat=True)


@register.filter(name='follow_request_exists')
def follow_request_exists(user, requester):
    ''' see if there is a pending follow request for a user '''
    try:
        models.UserFollowRequest.objects.filter(
            user_subject=requester,
            user_object=user,
        ).get()
        return True
    except models.UserFollowRequest.DoesNotExist:
        return False


@register.filter(name='boosted_status')
def get_boosted(boost):
    ''' load a boosted status. have to do this or it wont get foregin keys '''
    return models.Status.objects.select_subclasses().filter(
        id=boost.boosted_status.id
    ).get()


@register.filter(name='book_description')
def get_book_description(book):
    ''' use the work's text if the book doesn't have it '''
    return book.description or book.parent_work.description


@register.filter(name='uuid')
def get_uuid(identifier):
    ''' for avoiding clashing ids when there are many forms '''
    return '%s%s' % (identifier, uuid4())


@register.filter(name="post_date")
def time_since(date):
    ''' concise time ago function '''
    if not isinstance(date, datetime):
        return ''
    now = timezone.now()
    delta = now - date

    if date < (now - relativedelta(weeks=1)):
        formatter = '%b %-d'
        if date.year != now.year:
            formatter += ' %Y'
        return date.strftime(formatter)
    delta = relativedelta(now, date)
    if delta.days:
        return '%dd' % delta.days
    if delta.hours:
        return '%dh' % delta.hours
    if delta.minutes:
        return '%dm' % delta.minutes
    return '%ds' % delta.seconds


@register.simple_tag(takes_context=True)
def active_shelf(context, book):
    ''' check what shelf a user has a book on, if any '''
    shelf = models.ShelfBook.objects.filter(
        shelf__user=context['request'].user,
        book__in=book.parent_work.editions.all()
    ).first()
    return shelf if shelf else {'book': book}


@register.simple_tag(takes_context=False)
def latest_read_through(book, user):
    ''' the most recent read activity '''
    return models.ReadThrough.objects.filter(
        user=user,
        book=book
    ).order_by('-start_date').first()


@register.simple_tag(takes_context=False)
def active_read_through(book, user):
    ''' the most recent read activity '''
    return models.ReadThrough.objects.filter(
        user=user,
        book=book,
        finish_date__isnull=True
    ).order_by('-start_date').first()
