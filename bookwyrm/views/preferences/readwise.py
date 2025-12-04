"""Readwise integration settings view"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View

from bookwyrm import forms, models
from bookwyrm.connectors.readwise import (
    export_all_quotes_to_readwise,
    import_readwise_highlights,
)


@method_decorator(login_required, name="dispatch")
class ReadwiseSettings(View):
    """Readwise integration settings"""

    def get(self, request):
        """Display Readwise settings form"""
        # Get or create sync record for stats
        sync, _ = models.ReadwiseSync.objects.get_or_create(user=request.user)

        # Count stats
        total_quotes = models.Quotation.objects.filter(
            user=request.user, deleted=False
        ).count()
        exported_quotes = models.Quotation.objects.filter(
            user=request.user, deleted=False, readwise_highlight_id__isnull=False
        ).count()
        imported_highlights = models.ReadwiseSyncedHighlight.objects.filter(
            user=request.user, quotation__isnull=False
        ).count()
        unmatched_highlights = models.ReadwiseSyncedHighlight.objects.filter(
            user=request.user, quotation__isnull=True
        ).count()

        data = {
            "form": forms.ReadwiseSettingsForm(instance=request.user),
            "user": request.user,
            "sync": sync,
            "has_token": bool(request.user.readwise_token),
            "stats": {
                "total_quotes": total_quotes,
                "exported_quotes": exported_quotes,
                "imported_highlights": imported_highlights,
                "unmatched_highlights": unmatched_highlights,
            },
        }
        return TemplateResponse(request, "preferences/readwise.html", data)

    def post(self, request):
        """Save Readwise settings or trigger sync"""
        action = request.POST.get("action")

        if action == "export":
            return self._handle_export(request)
        elif action == "import":
            return self._handle_import(request)
        else:
            return self._handle_settings(request)

    def _handle_settings(self, request):
        """Save Readwise token and settings"""
        form = forms.ReadwiseSettingsForm(request.POST, instance=request.user)
        if not form.is_valid():
            sync, _ = models.ReadwiseSync.objects.get_or_create(user=request.user)
            data = {
                "form": form,
                "user": request.user,
                "sync": sync,
                "has_token": bool(request.user.readwise_token),
                "stats": self._get_stats(request.user),
            }
            return TemplateResponse(request, "preferences/readwise.html", data)

        form.save(request)

        # Create sync record if token was just added
        if request.user.readwise_token:
            models.ReadwiseSync.objects.get_or_create(user=request.user)

        messages.success(request, _("Readwise settings saved successfully."))
        return redirect("prefs-readwise")

    def _handle_export(self, request):
        """Trigger export of all quotes to Readwise"""
        if not request.user.readwise_token:
            messages.error(request, _("Please configure your Readwise token first."))
            return redirect("prefs-readwise")

        # Trigger async export
        transaction.on_commit(
            lambda: export_all_quotes_to_readwise.delay(request.user.id)
        )
        messages.success(
            request,
            _("Export started. Your quotes will be synced to Readwise in the background."),
        )
        return redirect("prefs-readwise")

    def _handle_import(self, request):
        """Trigger import of highlights from Readwise"""
        if not request.user.readwise_token:
            messages.error(request, _("Please configure your Readwise token first."))
            return redirect("prefs-readwise")

        # Trigger async import
        transaction.on_commit(
            lambda: import_readwise_highlights.delay(request.user.id)
        )
        messages.success(
            request,
            _("Import started. Readwise highlights will be imported in the background."),
        )
        return redirect("prefs-readwise")

    def _get_stats(self, user):
        """Get sync statistics for user"""
        return {
            "total_quotes": models.Quotation.objects.filter(
                user=user, deleted=False
            ).count(),
            "exported_quotes": models.Quotation.objects.filter(
                user=user, deleted=False, readwise_highlight_id__isnull=False
            ).count(),
            "imported_highlights": models.ReadwiseSyncedHighlight.objects.filter(
                user=user, quotation__isnull=False
            ).count(),
            "unmatched_highlights": models.ReadwiseSyncedHighlight.objects.filter(
                user=user, quotation__isnull=True
            ).count(),
        }
