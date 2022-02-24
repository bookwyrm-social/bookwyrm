""" moderation via flagged posts and users """
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.moderate_user", raise_exception=True),
    name="dispatch",
)
@method_decorator(
    permission_required("bookwyrm.moderate_post", raise_exception=True),
    name="dispatch",
)
# pylint: disable=no-self-use
class AutoMod(View):
    """Manage automated flagging"""

    def get(self, request):
        """view rules"""
        data = {"rules": models.AutoMod.objects.all(), "form": forms.AutoModRuleForm()}
        return TemplateResponse(request, "settings/automod/rules.html", data)

    def post(self, request):
        """add rule"""
        form = forms.AutoModRuleForm(request.POST)
        success = form.is_valid()
        if success:
            form.save()
            form = forms.AutoModRuleForm()

        data = {
            "rules": models.AutoMod.objects.all(),
            "form": form,
            "success": success,
        }
        return TemplateResponse(request, "settings/automod/rules.html", data)


@require_POST
@permission_required("bookwyrm.moderate_user", raise_exception=True)
@permission_required("bookwyrm.moderate_post", raise_exception=True)
# pylint: disable=unused-argument
def automod_delete(request, rule_id):
    """Remove a rule"""
    rule = get_object_or_404(models.AutoMod, id=rule_id)
    rule.delete()
    return redirect("settings-automod")


@require_POST
@permission_required("bookwyrm.moderate_user", raise_exception=True)
@permission_required("bookwyrm.moderate_post", raise_exception=True)
# pylint: disable=unused-argument
def run_automod(request):
    """run scan"""
    models.automod_task.delay()
    return redirect("settings-automod")
