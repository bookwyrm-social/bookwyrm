from django.contrib.postgres.search import TrigramSimilarity

from django.shortcuts import get_object_or_404, render

from bookwyrm.models.book import Genre, Book

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

    active_genres = []

    def post(self, request, *args, **kwargs):
        testList = request.POST.getlist('genres')

        for item in testList:
            print("Item successful captured!")
            print(item)
        
        self.active_genres = testList

        context = self.get_context_data()
        return render(request, self.template_name, context)

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self,*args, **kwargs):
        context = super(SearchGenre, self).get_context_data(*args,**kwargs)

        try:
            activeBooks = Book.objects.filter(genres = self.active_genres[0])
            for item in activeBooks:
                print(activeBooks)
            print("Active books successful")
        except:
            activeBooks = []
            print("Oh no, catatrophic failure! JIMMY, FETCH MY SUB")

        context['genre_tags'] = Genre.objects.all()
        context['listed_books'] = activeBooks
        return context
