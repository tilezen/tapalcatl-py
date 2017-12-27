import os


S3_BUCKET = os.environ.get("S3_BUCKET")
S3_PREFIX = os.environ.get("S3_PREFIX")
METATILE_SIZE = int(os.environ.get("METATILE_SIZE", '4'))
INCLUDE_HASH = os.environ.get("INCLUDE_HASH", 'true') == 'true'
