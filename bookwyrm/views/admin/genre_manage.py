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



class ManageGenreHome(TemplateView):
    template_name = 'settings/genres/genre_manage_home.html'

class ModifyGenre(TemplateView):
    template_name = 'settings/genres/genre_mod.html'

