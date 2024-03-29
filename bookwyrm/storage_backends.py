"""Handles backends for storages"""
from django.core.files.storage import FileSystemStorage
from storages.backends.s3 import S3Storage
from storages.backends.azure_storage import AzureStorage


class StaticStorage(S3Storage):  # pylint: disable=abstract-method
    """Storage class for Static contents"""

    location = "static"
    default_acl = "public-read"


class ImagesStorage(S3Storage):  # pylint: disable=abstract-method
    """Storage class for Image files"""

    location = "images"
    default_acl = "public-read"
    file_overwrite = False


class AzureStaticStorage(AzureStorage):  # pylint: disable=abstract-method
    """Storage class for Static contents"""

    location = "static"


class AzureImagesStorage(AzureStorage):  # pylint: disable=abstract-method
    """Storage class for Image files"""

    location = "images"
    overwrite_files = False


class ExportsFileStorage(FileSystemStorage):  # pylint: disable=abstract-method
    """Storage class for exports contents with local files"""

    location = "exports"
    overwrite_files = False


class ExportsS3Storage(S3Storage):  # pylint: disable=abstract-method
    """Storage class for exports contents with S3"""

    location = "exports"
    default_acl = None
    overwrite_files = False
