''' book list views'''
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseNotFound, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from .helpers import is_api_request, object_visible_to_user, privacy_filter


# pylint: disable=no-self-use
class Lists(View):
    ''' book list page '''
    def get(self, request):
        ''' display a book list '''
        user = request.user if request.user.is_authenticated else None
        lists = models.List.objects.filter(
            ~Q(user=user),
        ).all()
        lists = privacy_filter(request.user, lists, ['public', 'followers'])
        data = {
            'title': 'Lists',
            'lists': lists,
            'list_form': forms.ListForm()
        }
        return TemplateResponse(request, 'lists/lists.html', data)

    @method_decorator(login_required, name='dispatch')
    # pylint: disable=unused-argument
    def post(self, request):
        ''' create a book_list '''
        form = forms.ListForm(request.POST)
        if not form.is_valid():
            return redirect('lists')
        book_list = form.save()
        return redirect(book_list.local_path)


class List(View):
    ''' book list page '''
    def get(self, request, list_id):
        ''' display a book list '''
        book_list = get_object_or_404(models.List, id=list_id)
        if not object_visible_to_user(request.user, book_list):
            return HttpResponseNotFound()

        if is_api_request(request):
            return ActivitypubResponse(book_list.to_activity())

        suggestions = request.user.shelfbook_set.filter(
            ~Q(book__in=book_list.books.all())
        )

        data = {
            'title': '%s | Lists' % book_list.name,
            'list': book_list,
            'suggested_books': [s.book for s in suggestions[:5]],
            'list_form': forms.ListForm(instance=book_list),
        }
        return TemplateResponse(request, 'lists/list.html', data)


    @method_decorator(login_required, name='dispatch')
    # pylint: disable=unused-argument
    def post(self, request, list_id):
        ''' edit a book_list '''
        book_list = get_object_or_404(models.List, id=list_id)
        form = forms.ListForm(request.POST, instance=book_list)
        if not form.is_valid():
            return redirect('list', book_list.id)
        book_list = form.save()
        return redirect(book_list.local_path)


@require_POST
def add_book(request, list_id):
    ''' put a book on a list '''
    book_list = get_object_or_404(models.List, id=list_id)
    if not object_visible_to_user(request.user, book_list):
        return HttpResponseNotFound()

    book = get_object_or_404(models.Edition, id=request.POST.get('book'))
    # do you have permission to add to the list?
    if request.user == book_list.user or book_list.curation == 'open':
        # go ahead and add it
        models.ListItem.objects.create(
            book=book,
            book_list=book_list,
            added_by=request.user,
        )
    elif book_list.curation == 'curated':
        # make a pending entry
        models.ListItem.objects.create(
            approved=False,
            book=book,
            book_list=book_list,
            added_by=request.user,
        )
    else:
        # you can't add to this list, what were you THINKING
        return HttpResponseBadRequest()

    return redirect('list', list_id)
