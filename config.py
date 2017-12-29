import os


CORS_SEND_WILDCARD = True
CACHE_MAX_AGE = int(os.environ.get("CACHE_MAX_AGE", '600'))
S3_BUCKET = os.environ.get("S3_BUCKET")
S3_PREFIX = os.environ.get("S3_PREFIX")
METATILE_SIZE = int(os.environ.get("METATILE_SIZE", '4'))
INCLUDE_HASH = os.environ.get("INCLUDE_HASH", 'true') == 'true'
COMPRESS_MIMETYPES = [
    'application/x-protobuf',
    'application/json',
]
