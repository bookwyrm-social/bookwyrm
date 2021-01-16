''' non-interactive pages '''
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from .helpers import get_user_from_username, object_visible_to_user


# pylint: disable= no-self-use
@method_decorator(login_required, name='dispatch')
class Goal(View):
    ''' track books for the year '''
    def get(self, request, username, year):
        ''' reading goal page '''
        user = get_user_from_username(username)
        year = int(year)
        goal = models.AnnualGoal.objects.filter(
            year=year, user=user
        ).first()
        if not goal and user != request.user:
            return redirect('/')

        if goal and not object_visible_to_user(request.user, goal):
            return HttpResponseNotFound()

        data = {
            'title': '%s\'s %d Reading' % (user.display_name, year),
            'goal_form': forms.GoalForm(instance=goal),
            'goal': goal,
            'user': user,
            'year': year,
        }
        return TemplateResponse(request, 'goal.html', data)


    def post(self, request, username, year):
        ''' update or create an annual goal '''
        user = get_user_from_username(username)
        if user != request.user:
            return HttpResponseNotFound()

        year = int(year)
        goal = models.AnnualGoal.objects.filter(
            year=year, user=request.user
        ).first()
        form = forms.GoalForm(request.POST, instance=goal)
        if not form.is_valid():
            data = {
                'title': '%s\'s %d Reading' % (goal.user.display_name, year),
                'goal_form': form,
                'goal': goal,
                'year': year,
            }
            return TemplateResponse(request, 'goal.html', data)
        form.save()

        return redirect(request.headers.get('Referer', '/'))
