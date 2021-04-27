""" manage site settings """
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import emailing, forms, models


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class Site(View):
    """manage things like the instance name"""

    def get(self, request):
        """edit form"""
        site = models.SiteSettings.objects.get()
        data = {"site_form": forms.SiteForm(instance=site)}
        return TemplateResponse(request, "settings/site.html", data)

    def post(self, request):
        """edit the site settings"""
        site = models.SiteSettings.objects.get()
        form = forms.SiteForm(request.POST, request.FILES, instance=site)
        if not form.is_valid():
            data = {"site_form": form}
            return TemplateResponse(request, "settings/site.html", data)
        form.save()

        return redirect("settings-site")


@login_required
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def email_preview(request):
    """for development, renders and example email template"""
    template = request.GET.get("email")
    data = emailing.email_data()
    data["subject_path"] = "email/{}/subject.html".format(template)
    data["html_content_path"] = "email/{}/html_content.html".format(template)
    data["text_content_path"] = "email/{}/text_content.html".format(template)
    data["reset_link"] = "https://example.com/link"
    data["invite_link"] = "https://example.com/link"
    return TemplateResponse(request, "email/preview.html", data)
