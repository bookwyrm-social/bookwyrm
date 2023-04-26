""" manage imports """
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import models
from bookwyrm.views.helpers import redirect_to_referer
from bookwyrm.settings import PAGE_LENGTH


# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.moderate_user", raise_exception=True),
    name="dispatch",
)
class ImportList(View):
    """admin view of imports on this server"""

    def get(self, request, status="active"):
        """list of imports"""
        complete = status == "complete"

        sort = request.GET.get("sort", "created_date")
        sort_fields = [
            "created_date",
            "user",
        ]
        imports = models.ImportJob.objects.filter(complete=complete).order_by(
            "created_date"
        )
        # pylint: disable=consider-using-f-string
        if sort in sort_fields + ["-{:s}".format(f) for f in sort_fields]:
            imports = imports.order_by(sort)

        paginated = Paginator(imports, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))

        site_settings = models.SiteSettings.objects.get()
        data = {
            "imports": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "status": status,
            "sort": sort,
            "import_size_limit": site_settings.import_size_limit,
            "import_limit_reset": site_settings.import_limit_reset,
        }
        return TemplateResponse(request, "settings/imports/imports.html", data)

    # pylint: disable=unused-argument
    def post(self, request, import_id):
        """Mark an import as complete"""
        import_job = get_object_or_404(models.ImportJob, id=import_id)
        import_job.stop_job()
        return redirect_to_referer(request, "settings-imports")


@require_POST
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
# pylint: disable=unused-argument
def disable_imports(request):
    """When you just need people to please stop starting imports"""
    site = models.SiteSettings.objects.get()
    site.imports_enabled = False
    site.save(update_fields=["imports_enabled"])
    return redirect("settings-imports")


@require_POST
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
# pylint: disable=unused-argument
def enable_imports(request):
    """When you just need people to please stop starting imports"""
    site = models.SiteSettings.objects.get()
    site.imports_enabled = True
    site.save(update_fields=["imports_enabled"])
    return redirect("settings-imports")


@require_POST
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
# pylint: disable=unused-argument
def set_import_size_limit(request):
    """Limit the amount of books users can import at once"""
    site = models.SiteSettings.objects.get()
    import_size_limit = int(request.POST.get("limit"))
    import_limit_reset = int(request.POST.get("reset"))
    site.import_size_limit = import_size_limit
    site.import_limit_reset = import_limit_reset
    site.save(update_fields=["import_size_limit", "import_limit_reset"])
    return redirect("settings-imports")
