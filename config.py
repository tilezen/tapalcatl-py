import os


CORS_SEND_WILDCARD = True

# The max age for tiles returned by this service. Clients (both browsers and intermediate caches like CloudFront) will
# cache the tile this many seconds before checking with the origin to get a new tile.
# http://werkzeug.pocoo.org/docs/0.14/datastructures/#werkzeug.datastructures.ResponseCacheControl.max_age
CACHE_MAX_AGE = int(os.environ.get("CACHE_MAX_AGE", '1200'))

# The "shared" max age for tiles returned by this service. When an object is beyond this age in a shared cache (like CloudFront),
# the shared cache should check with the origin to see if the object was updated. In general, this number should be smaller than
# the max age set above.
# http://werkzeug.pocoo.org/docs/0.14/datastructures/#werkzeug.datastructures.ResponseCacheControl.s_maxage
SHARED_CACHE_MAX_AGE = int(os.environ.get("SHARED_CACHE_MAX_AGE", '600'))

CACHE_TYPE = os.environ.get('CACHE_TYPE', 'null')
CACHE_NO_NULL_WARNING = True
CACHE_REDIS_URL = os.environ.get('REDIS_URL')

METATILE_CACHE_SIZE = int(os.environ.get('METATILE_CACHE_SIZE', 0)) * 1000 * 1000
TILES_URL_BASE = os.environ.get('TILES_URL_BASE')
TILES_PREVIEW_API_KEY = os.environ.get('TILES_PREVIEW_API_KEY')
S3_BUCKET = os.environ.get("S3_BUCKET")
S3_PREFIX = os.environ.get("S3_PREFIX")
METATILE_SIZE = int(os.environ.get("METATILE_SIZE", '4'))
METATILE_MAX_DETAIL_ZOOM = int(os.environ.get("METATILE_MAX_DETAIL_ZOOM")) if os.environ.get("METATILE_MAX_DETAIL_ZOOM") else None
INCLUDE_HASH = os.environ.get("INCLUDE_HASH", 'true') == 'true'
REQUESTER_PAYS = os.environ.get("REQUESTER_PAYS", 'false') == 'true'

COMPRESS_MIMETYPES = [
    'application/x-protobuf',
    'application/json',
]
