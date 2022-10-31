from django.contrib.postgres.search import TrigramSimilarity
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from django.shortcuts import get_object_or_404, render

from bookwyrm.models.book import Genre, Book
from bookwyrm.models.suggestions import SuggestedGenre, MinimumVotesSetting
from bookwyrm.forms import SuggestionForm, MinimumVotesForm
from django.shortcuts import redirect

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
    DeleteView,
)


class GenreSuggestionsHome(ListView):
    """Get a list of all suggested genres in the admin page."""
    paginate_by = 15
    template_name = "settings/genres/genre_suggestions_home.html"
    model = SuggestedGenre


@method_decorator(login_required, name="dispatch")
class ApproveSuggestion(View):
    """approve a suggestion"""

    def post(self, request, pk):
        """approve a genre"""
        
        suggestion = SuggestedGenre.objects.get(id=pk)
        genre = Genre.objects.create_genre(suggestion.name, suggestion.description)
        genre.save()
        suggestion.delete()
        return redirect("settings-suggestions")


class ModifySuggestion(UpdateView):
    """Seperate page for modifying each genre in admin page."""

    template_name = "settings/genres/suggestion_mod.html"
    model = SuggestedGenre
    form_class = SuggestionForm
    success_url = reverse_lazy("settings-suggestions")


class RemoveSuggestion(DeleteView):
    template_name = "settings/genres/suggestion_delete.html"
    model = SuggestedGenre
    success_url = reverse_lazy("settings-suggestions")

class ModifyMinimumVotes(UpdateView):
    """Seperate page for modifying each genre in admin page."""

    template_name = "settings/genres/genre_suggestions_home.html"
    model = MinimumVotesSetting
    form_class = MinimumVotesForm
    success_url = reverse_lazy("settings-suggestions")