from django.contrib.postgres.search import TrigramSimilarity

from django.shortcuts import get_object_or_404, render

from bookwyrm.models.book import Genre, Book

from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.db.models.functions import Greatest
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views import View
from django.views.generic import (
    CreateView,
    ListView,
    UpdateView,
)



class ManageGenreHome(ListView):
    template_name = 'settings/genres/genre_manage_home.html'
    model = Genre

class ModifyGenre(UpdateView):
    template_name = 'settings/genres/genre_mod.html'
    fields = ['genre_name', 'description']
    model = Genre

class CreateGenre(CreateView):
    template_name = 'settings/genres/genre_add.html'
    model = Genre
    success_url = reverse_lazy('settings-genres')
    fields = ['genre_name', 'description']

