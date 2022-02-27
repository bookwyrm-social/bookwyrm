""" manage themes """
from django.contrib.auth.decorators import login_required, permission_required
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class Themes(View):
    """manage things like the instance name"""

    def get(self, request):
        """view existing themes and set defaults"""
        data = {
            "themes": models.Theme.objects.all(),
            "theme_form": forms.ThemeForm(),
        }
        return TemplateResponse(request, "settings/themes.html", data)

    def post(self, request):
        """edit the site settings"""
        form = forms.ThemeForm(request.POST, request.FILES)
        data = {
            "themes": models.Theme.objects.all(),
            "theme_form": form,
        }
        if form.is_valid():
            form.save()
            data["success"] = True
            data["theme_form"] = forms.ThemeForm()
        return TemplateResponse(request, "settings/themes.html", data)
