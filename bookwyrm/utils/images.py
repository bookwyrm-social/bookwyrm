""" Image  utilities """

from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile


def remove_uploaded_image_exif(source: InMemoryUploadedFile) -> InMemoryUploadedFile:
    """Removes EXIF data from provided image and returns a sanitized copy"""
    io = BytesIO()
    with Image.open(source) as image:
        if "exif" in image.info:
            del image.info["exif"]

        if image.format == "JPEG":
            image.save(io, format=image.format, quality="keep")
        else:
            image.save(io, format=image.format)

    return InMemoryUploadedFile(
        io,
        source.field_name,
        source.name,
        source.content_type,
        len(io.getvalue()),
        source.charset,
    )
