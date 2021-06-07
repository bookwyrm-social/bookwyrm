from storages.backends.s3boto3 import S3Boto3Storage

class StaticStorage(S3Boto3Storage):
    location = 'static'
    default_acl = 'public-read'


class ImagesStorage(S3Boto3Storage):
    location = 'images'
    default_acl = 'public-read'
    file_overwrite = False