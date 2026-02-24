import re
import logging
import tempfile
from PIL import Image
from environs import Env
from io import BytesIO

from django.core.files import File
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.utils.decorators import method_decorator
from django.views import View
from django.http import JsonResponse

from bookwyrm import models

logger = logging.getLogger(__name__)

PREFERRED_EXTENSIONS = {img_type: ext for ext, img_type in Image.registered_extensions().items()}
PREFERRED_EXTENSIONS.update(
    {
        "JPEG": ".jpg",
        "PNG": ".png",
        "TIFF": ".tif",
    }
)


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class CreateUserUpload(View):
    def post(self, request):
        file = request.FILES["file"]
        image = Image.open(file)
        upload = models.UserUpload(
            user=request.user,
            original_name=file.name,
            original_content_type=file.content_type,
            original_file=file,
        )
        upload.save()

        width, height = image.size
        env = Env()
        sizes = env.list("UPLOAD_IMAGE_SIZES", [400, 1200], subcast=int)

        for size in sizes:
            v = self.create_version(image, upload, size)
            if width < size and height < size:
                break

        biggest = upload.versions.order_by("-max_dimension")[0]
        return JsonResponse(
            {
                "name": upload.original_file.name,
                "url": request.build_absolute_uri(biggest.file.url),
            },
            status=201,
        )

    def create_version(self, image, user_upload, max_dimension):
        image_format = image.format
        width, height = image.size
        target_width, target_height = target_size(width, height, max_dimension)
        if target_width != width or target_height != height:
            image = image.resize([target_width, target_height])

        img_byte_arr = BytesIO()
        image.save(img_byte_arr, image_format)

        ext = PREFERRED_EXTENSIONS[image_format]

        return user_upload.versions.create(
            max_dimension=max_dimension,
            user_upload=user_upload,
            file=File(img_byte_arr, name="resized{0}".format(ext)),
        )


def target_size(width, height, max_dimension):
    if width < max_dimension and height < max_dimension:
        return [width, height]
    elif width > height:
        return [max_dimension, round(height * (max_dimension / width))]
    else:
        return [round(width * (max_dimension / height)), max_dimension]
