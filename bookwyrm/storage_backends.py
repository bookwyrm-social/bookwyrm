"""Handles backends for storages"""
from storages.backends.s3boto3 import S3Boto3Storage


class StaticStorage(S3Boto3Storage):  # pylint: disable=abstract-method
    """Storage class for Static contents"""

    location = "static"
    default_acl = "public-read"


class ImagesStorage(S3Boto3Storage):  # pylint: disable=abstract-method
    """Storage class for Image files"""

    location = "images"
    default_acl = "public-read"
    file_overwrite = False
