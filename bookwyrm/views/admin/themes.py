""" manage themes """
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.system_administration", raise_exception=True),
    name="dispatch",
)
class Themes(View):
    """manage things like the instance name"""

    def get(self, request):
        """view existing themes and set defaults"""
        return TemplateResponse(request, "settings/themes.html", get_view_data())

    def post(self, request):
        """edit the site settings"""
        form = forms.ThemeForm(request.POST)
        if form.is_valid():
            form.save(request)

        data = get_view_data()

        if not form.is_valid():
            data["theme_form"] = form
        else:
            data["success"] = True
        return TemplateResponse(request, "settings/themes.html", data)


def get_view_data():
    """data for view"""
    return {
        "themes": models.Theme.objects.all(),
        "theme_form": forms.ThemeForm(),
    }


@require_POST
@permission_required("bookwyrm.system_administration", raise_exception=True)
# pylint: disable=unused-argument
def delete_theme(request, theme_id):
    """Remove a theme"""
    get_object_or_404(models.Theme, id=theme_id).delete()
    return redirect("settings-themes")
