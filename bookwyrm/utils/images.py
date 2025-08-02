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
        if isinstance(source, InMemoryUploadedFile):
            source_buffer = BytesIO(source.read())
            with Image.open(source_buffer) as image:
                if "exif" in image.info:
                    del image.info["exif"]
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
                return source
        if isinstance(source, TemporaryUploadedFile):
            uploaded_file_path = source.temporary_file_path()
            with Image.open(uploaded_file_path) as image:
                if "exif" in image.info:
                    del image.info["exif"]
                    image.save(uploaded_file_path)
        return source
    except (OSError, UnidentifiedImageError):
        logger.exception(
            "Could not open image file for EXIF removal, saving unmodified image"
        )
    return source
