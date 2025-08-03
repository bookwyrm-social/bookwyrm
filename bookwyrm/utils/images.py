""" Image  utilities """

import logging
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from django.core.files.uploadedfile import (
    UploadedFile,
    InMemoryUploadedFile,
    TemporaryUploadedFile,
)

logger = logging.getLogger(__name__)


def remove_uploaded_image_exif(source: UploadedFile) -> UploadedFile:
    """Removes EXIF data from provided image and returns a sanitized copy"""
    try:
        with Image.open(source) as image:
            if "exif" not in image.info:
                return source
            del image.info["exif"]
            if isinstance(source, InMemoryUploadedFile):
                output_buffer = BytesIO()
                if image.format == "JPEG":
                    image.save(output_buffer, format=image.format, quality="keep")
                else:
                    image.save(output_buffer, format=image.format)
                output_buffer.seek(0)
                return InMemoryUploadedFile(
                    output_buffer,
                    source.field_name,
                    source.name,
                    source.content_type,
                    len(output_buffer.getvalue()),
                    source.charset,
                )
            if isinstance(source, TemporaryUploadedFile):
                image.save(source.temporary_file_path())
    except (OSError, UnidentifiedImageError):
        logger.exception(
            "Could not open image file for EXIF removal, saving unmodified image"
        )
    return source
