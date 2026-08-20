from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator

from bookwyrm.views.helpers import is_api_request, get_user_from_username
from bookwyrm.views.helpers import redirect_to_referer


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

        if profile_user.is_profile_visible_to(request.user.id):
            return super().dispatch(request, *args, **kwargs)

        return TemplateResponse(
            request,
            "user/user.html",
            {"user": profile_user, "is_self": False, "is_profile_locked": True},
        )


class MergeableViewMixin:
    @method_decorator(login_required, name="dispatch")
    @method_decorator(
        permission_required("bookwyrm.edit_book", raise_exception=True), name="dispatch"
    )
    def post(self, request, book_id, **kwargs):
        """Prevent objects from being merged"""
        obj = get_object_or_404(
            self.merge_model, id=book_id, pending_merge_target__isnull=False
        )
        obj.prevent_automatic_merge = True
        obj.save(broadcast=False, update_fields=["prevent_automatic_merge"])
        return redirect_to_referer(request)
