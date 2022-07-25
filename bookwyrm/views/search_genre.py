from django.contrib.postgres.search import TrigramSimilarity

from django.shortcuts import get_object_or_404, render

from bookwyrm.models.book import Genre

from django.core.paginator import Paginator
from django.db.models.functions import Greatest
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views import View
from django.views.generic import (
    TemplateView,
)

class SearchGenre(TemplateView):
    template_name = 'search/genre_search.html'

    def post(self, request, *args, **kwargs):
        testList = request.POST.getlist('genres')

        for item in testList:
            print("Item successful captured!")
            print(item)

        context = self.get_context_data()
        return render(request, self.template_name, context)

    def get_context_data(self,*args, **kwargs):
        context = super(SearchGenre, self).get_context_data(*args,**kwargs)
        context['genre_tags'] = Genre.objects.all()
        return context

    