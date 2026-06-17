from django.template.response import TemplateResponse

from bookwyrm.views.helpers import is_api_request, get_user_from_username


class PrivateProfileMixin:
    def dispatch(self, request, *args, **kwargs):
        username = kwargs.get("username")
        if not username:
            # This should not be reached unless the mixin is used on an inappropriate view,
            # in that case, treat it as a no-op
            return super().dispatch(request, *args, **kwargs)

        profile_user = get_user_from_username(request.user, username)
        request.profile_user = profile_user
        if is_api_request(request):
            # The API reveals no private activities.
            return super().dispatch(request, *args, **kwargs)


        is_self = request.user.is_authenticated and profile_user.id == request.user.id
        if is_self or profile_user.is_profile_visible_to(request.user.id):
            return super().dispatch(request, *args, **kwargs)

        return TemplateResponse(
            request,
            "user/user.html",
            {"user": profile_user, "is_self": False, "is_profile_locked": True},
        )
