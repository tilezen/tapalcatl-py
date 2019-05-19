import os


CORS_SEND_WILDCARD = True

# The max age for tiles returned by this service. Clients (both browsers and intermediate caches like CloudFront) will
# cache the tile this many seconds before checking with the origin to get a new tile.
# http://werkzeug.pocoo.org/docs/0.14/datastructures/#werkzeug.datastructures.ResponseCacheControl.max_age
CACHE_MAX_AGE = int(os.environ.get("CACHE_MAX_AGE", '2419200'))

# The "shared" max age for tiles returned by this service. When an object is beyond this age in a shared cache (like CloudFront),
# the shared cache should check with the origin to see if the object was updated. In general, this number should be smaller than
# the max age set above.
# http://werkzeug.pocoo.org/docs/0.14/datastructures/#werkzeug.datastructures.ResponseCacheControl.s_maxage
SHARED_CACHE_MAX_AGE = int(os.environ.get("SHARED_CACHE_MAX_AGE", '1209600'))

CACHE_TYPE = os.environ.get('CACHE_TYPE', 'null')
CACHE_NO_NULL_WARNING = True
# Expose some of the caching config via environment variables
# so we can have more freedom to configure this in-situ.
CACHE_REDIS_URL = os.environ.get('CACHE_REDIS_URL')
CACHE_THRESHOLD = int(os.environ.get('CACHE_THRESHOLD')) if os.environ.get('CACHE_THRESHOLD') else None
CACHE_KEY_PREFIX = os.environ.get('CACHE_KEY_PREFIX')
CACHE_DIR = os.environ.get('CACHE_DIR')

TILES_URL_BASE = os.environ.get('TILES_URL_BASE')
TILES_PREVIEW_API_KEY = os.environ.get('TILES_PREVIEW_API_KEY')
S3_BUCKET = os.environ.get("S3_BUCKET")
S3_PREFIX = os.environ.get("S3_PREFIX")
S3_LAYER = os.environ.get("S3_LAYER", "all")
METATILE_SIZE = int(os.environ.get("METATILE_SIZE", '4'))
METATILE_MAX_DETAIL_ZOOM = int(os.environ.get("METATILE_MAX_DETAIL_ZOOM")) if os.environ.get("METATILE_MAX_DETAIL_ZOOM") else None
INCLUDE_HASH = os.environ.get("INCLUDE_HASH") == 'true' if os.environ.get("INCLUDE_HASH") else None
KEY_FORMAT_TYPE = os.environ.get("KEY_FORMAT_TYPE")
REQUESTER_PAYS = os.environ.get("REQUESTER_PAYS", 'false') == 'true'

COMPRESS_MIMETYPES = [
    'application/x-protobuf',
    'application/json',
]

# Landcover layer is built using Tapalcatl2 archives that require a bit of extra configuration:
# The maximum zoom level for the landcover data is different than the vector tiles
LANDCOVER_MAX_ZOOM = 13
# Tapalcatl2 archives are "materialized" at particular zoom levels at build time.
# These are the zooms we picked when building the landcover layer
LANDCOVER_MATERIALIZED_ZOOMS = [0, 7]
# Tapalcatl2 archives can contain multiple neighboring tiles to form a "metatile"
# THe landcover build used a metatile size of 1
LANDCOVER_METATILE_SIZE = 1
