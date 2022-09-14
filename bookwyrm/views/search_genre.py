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
    search_is_AND = False

    def post(self, request, *args, **kwargs):
        '''Get the genres the user has selected.'''
        testList = request.POST.getlist('genres')

        for item in testList:
            print("Item successful captured!")
            print(item)
        
        self.active_genres = testList

        buttonSelection = request.POST.get("search_buttons")
        print(buttonSelection)
        if buttonSelection == "search_and":
            self.search_is_AND = True
            print("AND searching activated")
        else:
            self.search_is_AND = False

        context = self.get_context_data()
        return render(request, self.template_name, context)

    def get(self, request, *args, **kwargs):
        '''Render our template to the user. It will have a list of all available genres.'''
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self,*args, **kwargs):
        '''Get our genre list and put them on the page. If the user made a query, also display the books.'''
        context = super(SearchGenre, self).get_context_data(*args,**kwargs)

        # Check if there's actually a genre selected.
        if(len(self.active_genres)):
            activeBooks = []
            if self.search_is_AND:
                print("Searching using AND")
                base_qs = Book.objects.all()
                for gen in self.active_genres:
                    activeBooks = base_qs.filter(genres__pk__contains=gen)
            else:
                for gen in self.active_genres:
                    print("Item successful captured!")

                    #if True:
                    #    filterGenres = []
                    #    for filterGen in self.active_genres:
                    #        filterGenres.append(filterGen)

                    #activeBooks.extend(Book.objects.filter(genres = gen))
                    activeBooks.extend(Book.objects.filter(genres = gen))


            print("Printing this enter:" + self.active_genres[0])
            for item in activeBooks:
                print(item)
            print("Active books successful")
        else:
            activeBooks = []
            print("Empty List") 



        context['genre_tags'] = Genre.objects.all()
        context['listed_books'] = activeBooks
        return context

