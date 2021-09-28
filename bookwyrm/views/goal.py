""" non-interactive pages """
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.template.loader import get_template
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.status import create_generated_note
from .helpers import get_user_from_username


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Goal(View):
    """track books for the year"""

    def get(self, request, username, year):
        """reading goal page"""
        user = get_user_from_username(request.user, username)
        year = int(year)
        goal = models.AnnualGoal.objects.filter(year=year, user=user).first()
        if not goal and user != request.user:
            return HttpResponseNotFound()

        current_year = timezone.now().year
        if not goal and year != timezone.now().year:
            return redirect("user-goal", username, current_year)

        if goal:
            goal.raise_visible_to_user(request.user)

        data = {
            "goal_form": forms.GoalForm(instance=goal),
            "goal": goal,
            "user": user,
            "year": year,
            "is_self": request.user == user,
        }
        return TemplateResponse(request, "user/goal.html", data)

    def post(self, request, username, year):
        """update or create an annual goal"""
        year = int(year)
        user = get_user_from_username(request.user, username)
        goal = models.AnnualGoal.objects.filter(year=year, user=user).first()
        if goal:
            goal.raise_not_editable(request.user)

        form = forms.GoalForm(request.POST, instance=goal)
        if not form.is_valid():
            data = {
                "goal_form": form,
                "goal": goal,
                "year": year,
            }
            return TemplateResponse(request, "user/goal.html", data)
        goal = form.save()

        if request.POST.get("post-status"):
            # create status, if appropriate
            template = get_template("snippets/generated_status/goal.html")
            create_generated_note(
                request.user,
                template.render({"goal": goal, "user": user}).strip(),
                privacy=goal.privacy,
            )

        return redirect(request.headers.get("Referer", "/"))


@require_POST
@login_required
def hide_goal(request):
    """don't keep bugging people to set a goal"""
    request.user.show_goal = False
    request.user.save(broadcast=False, update_fields=["show_goal"])
    return redirect(request.headers.get("Referer", "/"))
