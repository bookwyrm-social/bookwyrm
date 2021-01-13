''' non-interactive pages '''
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Max
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.settings import PAGE_LENGTH
from .helpers import get_activity_feed


# pylint: disable= no-self-use
@method_decorator(login_required, name='dispatch')
class About(View):
    ''' create invites '''
    def get(self, request):
        ''' more information about the instance '''
        data = {
            'title': 'About',
        }
        return TemplateResponse(request, 'about.html', data)

class Home(View):
    ''' discover page or home feed depending on auth '''
    def get(self, request):
        ''' this is the same as the feed on the home tab '''
        if request.user.is_authenticated:
            feed_view = Feed.as_view()
            return feed_view(request, 'home')
        discover_view = Discover.as_view()
        return discover_view(request)

class Discover(View):
    ''' preview of recently reviewed books '''
    def get(self, request):
        ''' tiled book activity page '''
        books = models.Edition.objects.filter(
            review__published_date__isnull=False,
            review__user__local=True,
            review__privacy__in=['public', 'unlisted'],
        ).exclude(
            cover__exact=''
        ).annotate(
            Max('review__published_date')
        ).order_by('-review__published_date__max')[:6]

        ratings = {}
        for book in books:
            reviews = models.Review.objects.filter(
                book__in=book.parent_work.editions.all()
            )
            reviews = get_activity_feed(
                request.user, ['public', 'unlisted'], queryset=reviews)
            ratings[book.id] = reviews.aggregate(Avg('rating'))['rating__avg']
        data = {
            'title': 'Discover',
            'register_form': forms.RegisterForm(),
            'books': list(set(books)),
            'ratings': ratings
        }
        return TemplateResponse(request, 'discover.html', data)


@method_decorator(login_required, name='dispatch')
class Feed(View):
    ''' activity stream '''
    def get(self, request, tab):
        ''' user's homepage with activity feed '''
        try:
            page = int(request.GET.get('page', 1))
        except ValueError:
            page = 1

        suggested_books = get_suggested_books(request.user)

        if tab == 'home':
            activities = get_activity_feed(
                request.user, ['public', 'unlisted', 'followers'],
                following_only=True)
        elif tab == 'local':
            activities = get_activity_feed(
                request.user, ['public', 'followers'], local_only=True)
        else:
            activities = get_activity_feed(
                request.user, ['public', 'followers'])
        paginated = Paginator(activities, PAGE_LENGTH)
        data = {
            'title': 'Updates Feed',
            'user': request.user,
            'suggested_books': suggested_books,
            'activities': paginated.page(page),
            'tab': tab,
        }
        return TemplateResponse(request, 'feed.html', data)


def get_suggested_books(user, max_books=5):
    ''' helper to get a user's recent books '''
    book_count = 0
    preset_shelves = [
        ('reading', max_books), ('read', 2), ('to-read', max_books)
    ]
    suggested_books = []
    for (preset, shelf_max) in preset_shelves:
        limit = shelf_max if shelf_max < (max_books - book_count) \
                else max_books - book_count
        shelf = user.shelf_set.get(identifier=preset)

        shelf_books = shelf.shelfbook_set.order_by(
            '-updated_date'
        ).all()[:limit]
        if not shelf_books:
            continue
        shelf_preview = {
            'name': shelf.name,
            'books': [s.book for s in shelf_books]
        }
        suggested_books.append(shelf_preview)
        book_count += len(shelf_preview['books'])
    return suggested_books
