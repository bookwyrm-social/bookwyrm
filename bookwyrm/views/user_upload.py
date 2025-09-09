import re
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.utils.decorators import method_decorator
from django.views import View
from django.http import JsonResponse

from bookwyrm import models

logger = logging.getLogger(__name__)

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class CreateUserUpload(View):
    def post(self, request):
        file = request.FILES['file']
        upload = models.UserUpload(
                    user=request.user,
                    file=file,
                    original_name=file.name,
                    original_content_type=file.content_type
                )
        upload.save()
        return JsonResponse({
                "url": request.build_absolute_uri(upload.file.url)
            })
