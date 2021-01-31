''' book list views'''
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import models
from bookwyrm.activitypub import ActivitypubResponse
from .helpers import is_api_request


# pylint: disable=no-self-use
class Lists(View):
    ''' book list page '''
    def get(self, request):
        ''' display a book list '''
        user = request.user if request.user.is_authenticated else None
        lists = models.List.objects.filter(~Q(user=user)).all()
        return TemplateResponse(request, 'lists/lists.html', {'lists': lists})

    @method_decorator(login_required, name='dispatch')
    # pylint: disable=unused-argument
    def post(self, request):
        ''' create a book_list '''
        book_list = None
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
        data = {
            'list': book_list
        }
        return TemplateResponse(request, 'lists/list.html', data)


    @method_decorator(login_required, name='dispatch')
    # pylint: disable=unused-argument
    def post(self, request, list_id):
        ''' create a book_list '''
        book_list = get_object_or_404(models.List, id=list_id)
        return redirect(book_list.local_path)
