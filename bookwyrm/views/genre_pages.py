from django.contrib.postgres.search import TrigramSimilarity

from django.shortcuts import get_object_or_404, render

from bookwyrm.models.book import Genre, Book
from bookwyrm.forms import GenreForm

from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.db.models.functions import Greatest
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views import View
from django.views.generic import (
    DetailView,
    ListView,
)

class ManageGenreHome(DetailView):
    template_name = 'genre/test.html'
    model = Genre