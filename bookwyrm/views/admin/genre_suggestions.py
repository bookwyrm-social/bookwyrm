from django.contrib.postgres.search import TrigramSimilarity
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from django.shortcuts import get_object_or_404, render

from bookwyrm.models.book import Genre, Book, Edition
from bookwyrm.models.suggestions import SuggestedGenre, MinimumVotesSetting, SuggestedBookGenre
from bookwyrm.forms import SuggestionForm
from django.shortcuts import redirect

from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.db.models.functions import Greatest
from django.db.models import Q
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
    def get_ordering(self):
        if self.request.GET.get('sort'):
            order = self.request.GET.get('sort')
            if order == 'votes':
                ordering = '-' + order
            else:
                ordering = order
            return ordering
        else:
            ordering = ['name']
            return ordering


    def get(self, request, *args, **kwargs):
        min_vote = request.GET.get("minimum_gen_vote")
        # If the minimum vote was modified, it'll read that and change as needed.
        if min_vote:
            VotesSetting = MinimumVotesSetting.objects.get(id=1)
            VotesSetting.minimum_genre_votes = min_vote
            VotesSetting.save()
        print(min_vote)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        if not MinimumVotesSetting.objects.all().exists():
            MinimumVotesSetting.objects.create()

        VotesSetting = MinimumVotesSetting.objects.get(id=1)
        context = super().get_context_data(**kwargs)
        context["minimum_votes_get"] = VotesSetting.minimum_genre_votes
        return context


@method_decorator(login_required, name="dispatch")
class ApproveSuggestion(View):
    """approve a genre suggestion"""

    def post(self, request, pk):
        """approve a genre"""

        suggestion = SuggestedGenre.objects.get(id=pk)
        genre = Genre.objects.create_genre(suggestion.name, suggestion.description)
        genre.save()
        suggestion.delete()
        return redirect("settings-suggestions")


class ModifySuggestion(UpdateView):
    """Separate page for modifying each genre suggestion in admin page."""

    template_name = "settings/genres/suggestion_mod.html"
    model = SuggestedGenre
    form_class = SuggestionForm
    success_url = reverse_lazy("settings-suggestions")


class RemoveSuggestion(DeleteView):
    template_name = "settings/genres/suggestion_delete.html"
    model = SuggestedGenre
    success_url = reverse_lazy("settings-suggestions")


class BookGenreSuggestionsHome(ListView):
    """Get a list of all suggested genres for books in the admin page."""
    paginate_by = 15
    template_name = "settings/genres/book_suggestions_home.html"
    model = SuggestedBookGenre
    def get_ordering(self):
        if self.request.GET.get('sort'):
            order = self.request.GET.get('sort')
            if order == 'votes':
                ordering = '-' + order
            else:
                ordering = order
            return ordering
        else:
            ordering = ['genre__genre_name']
            return ordering


    def get(self, request, *args, **kwargs):
        min_vote = request.GET.get("minimum_gen_vote")
        # If the minimum vote was modified, it'll read that and change as needed.
        if min_vote:
            VotesSetting = MinimumVotesSetting.objects.get(id=1)
            VotesSetting.minimum_book_votes = min_vote
            VotesSetting.save()
        print(min_vote)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        if not MinimumVotesSetting.objects.all().exists():
            MinimumVotesSetting.objects.create()

        VotesSetting = MinimumVotesSetting.objects.get(id=1)
        context = super().get_context_data(**kwargs)
        context["minimum_votes_get"] = VotesSetting.minimum_book_votes
        return context


@method_decorator(login_required, name="dispatch")
class ApproveBookSuggestion(View):
    """approve a book genre suggestion"""

    def post(self, request, pk):
        """approve a genre"""

        suggestion = SuggestedBookGenre.objects.get(id=pk)
        genre = suggestion.genre
        work = suggestion.book
        work.genres.add(genre)
        editions = Edition.objects.filter(Q(parent_work=work))
        for edition in editions:
            edition.genres.add(genre)
        suggestion.delete()
        return redirect("settings-book-suggestions")


class RemoveBookSuggestion(DeleteView):
    template_name = "settings/genres/book_suggestion_delete.html"
    model = SuggestedBookGenre
    success_url = reverse_lazy("settings-book-suggestions")