import boto3
import botocore
import dateutil.parser
import hashlib
import logging
import math
import time
import zipfile
from collections import namedtuple
from io import BytesIO
from flask import Blueprint, Flask, current_app, make_response, render_template, request, abort
from flask_caching import Cache
from flask_compress import Compress
from flask_cors import CORS

# make compatible with both 3.4+, which has enum built in, and <=3.3 which
# doesn't.
try:
    from enum import Enum
except ImportError:
    from enum34 import Enum


tile_bp = Blueprint('tiles', __name__)
cache = Cache()


def create_app():
    app = Flask(__name__)
    app.config.from_object('config')
    CORS(app)
    Compress(app)
    cache.init_app(app)
    app.boto_s3 = boto3.client('s3')

    @app.before_first_request
    def setup_logging():
        if not app.debug:
            # In production mode, add log handler to sys.stderr.
            app.logger.addHandler(logging.StreamHandler())
            app.logger.setLevel(logging.INFO)

    app.register_blueprint(tile_bp)

    return app


MIME_TYPES = {
    "json": "application/json",
    "mvt": "application/x-protobuf",
    "mvtb": "application/x-protobuf",
    "topojson": "application/json",
}
TileRequest = namedtuple('TileRequest', ['z', 'x', 'y', 'format'])
CacheInfo = namedtuple('CacheInfo', ['last_modified', 'etag'])
StorageResponse = namedtuple('StorageResponse', ['data', 'cache_info'])


class MetatileNotModifiedException(Exception):
    pass


class MetatileNotFoundException(Exception):
    pass


class UnknownMetatileException(Exception):
    pass


class TileNotFoundInMetatile(Exception):
    pass


def is_power_of_two(num):
    return num and not num & (num - 1)


def size_to_zoom(size):
    return math.log(size, 2)


def meta_and_offset(requested_tile, meta_size, tile_size,
                    metatile_max_detail_zoom=None):
    if not is_power_of_two(meta_size):
        raise ValueError("Metatile size %s is not a power of two" % meta_size)
    if not is_power_of_two(tile_size):
        raise ValueError("Tile size %s is not a power of two" % tile_size)

    meta_zoom = size_to_zoom(meta_size)
    tile_zoom = size_to_zoom(tile_size)

    if tile_zoom > meta_zoom:
        raise ValueError(
            "Tile size must not be greater than metatile size, "
            "but %d > %d." % (tile_size, meta_size))

    delta_z = int(meta_zoom - tile_zoom)

    # clip the top of the range, as we don't ever have tiles with negative
    # zooms. this might change the effective delta between the zoom level of
    # the request and the zoom level of the metatile.
    if requested_tile.z < delta_z:
        meta = TileRequest(0, 0, 0, 'zip')
    else:

        # allows setting a maximum detail level beyond which all features are
        # present in the tile and requests with tile_size larger than are
        # available can be satisfied with "smaller" tiles that are present.
        if metatile_max_detail_zoom and \
           requested_tile.z - delta_z > metatile_max_detail_zoom:
            # the call to min() is here to clamp the size of the offset - the
            # idea being that it's better to request a metatile that isn't
            # present and 404, rather than request one that is, pay the cost
            # of unzipping it, and find it doesn't contain the offset.
            delta_z = min(requested_tile.z - metatile_max_detail_zoom,
                          int(meta_zoom))

        meta = TileRequest(
            requested_tile.z - delta_z,
            requested_tile.x >> delta_z,
            requested_tile.y >> delta_z,
            'zip',
        )

    actual_delta_z = requested_tile.z - meta.z
    offset = TileRequest(
        actual_delta_z,
        requested_tile.x - (meta.x << actual_delta_z),
        requested_tile.y - (meta.y << actual_delta_z),
        requested_tile.format,
    )

    return meta, offset


class KeyFormatType(Enum):
    """
    S3 key format options; either no hash, the hash followed by the prefix, or
    the prefix followed by the hash. For example, for metatile 10/511/430 in
    the 'all' layer:

     * no_hash:     /180723/all/10/511/430.zip
     * hash_prefix: /0035e/180723/all/10/511/430.zip
     * prefix_hash: /180723/0035e/all/10/511/430.zip
    """

    NO_HASH = "{prefix}{suffix}"
    HASH_PREFIX = "{hash}{prefix}{suffix}"
    PREFIX_HASH = "{prefix}{hash}{suffix}"


def compute_key(prefix, layer, meta_tile,
                key_format_type=KeyFormatType.NO_HASH):
    k = "{z}/{x}/{y}.{fmt}".format(
        z=meta_tile.z,
        x=meta_tile.x,
        y=meta_tile.y,
        fmt=meta_tile.format,
    )

    # in versions of code before https://github.com/tilezen/tilequeue/pull/344,
    # we included the layer and leading slash in the hashed string. after that
    # PR, we no longer support having a layer in the path and _also_ drop the
    # leading slash from the hashed string.
    if layer:
        k = "/{layer}/{suffix}".format(
            layer=layer,
            suffix=k
        )

    # make sure each part is either empty or starts with a /, that means that
    # they will combine to make a valid path.
    h = "/" + hashlib.md5(k.encode('utf8')).hexdigest()[:5]
    prefix = "/" + prefix if prefix else ""

    if not layer:
        # in the case where layer wasn't provided and we didn't hash the
        # leading slash, we still need to add a leading slash so that it makes
        # valid path.
        k = "/" + k

    k = key_format_type.value.format(
        hash=h,
        prefix=prefix,
        suffix=k,
    )

    # Strip off the leading slash
    return k[1:]


def metatile_fetch(meta, cache_info):
    cached = cache.get(meta)
    if cached:
        current_app.logger.info("%s: Using a cached metatile", meta)
        return cached

    s3_key_prefix = current_app.config.get('S3_PREFIX')
    include_hash = current_app.config.get('INCLUDE_HASH')
    key_format_type = current_app.config.get('KEY_FORMAT_TYPE')
    s3_key_layer = current_app.config.get('S3_LAYER')
    requester_pays = current_app.config.get('REQUESTER_PAYS')

    if key_format_type:
        key_format_type = KeyFormatType[key_format_type]
    elif include_hash == False:
        # map include_hash onto key format types for backwards compatibility
        key_format_type = KeyFormatType.NO_HASH
    else:
        # note that prefix-hash is the default if neither config parameter is
        # provided!
        key_format_type = KeyFormatType.PREFIX_HASH

    s3_bucket = current_app.config.get('S3_BUCKET')
    s3_key = compute_key(s3_key_prefix, s3_key_layer, meta, key_format_type)

    get_params = {
        "Bucket": s3_bucket,
        "Key": s3_key,
    }

    if cache_info.last_modified:
        get_params['IfModifiedSince'] = cache_info.last_modified

    if cache_info.etag:
        get_params['IfNoneMatch'] = cache_info.etag

    if requester_pays:
        get_params['RequestPayer'] = 'requester'

    try:
        a = time.time()
        response = current_app.boto_s3.get_object(**get_params)

        # Strip the quotes that boto includes
        quoteless_etag = response['ETag'][1:-1]
        result = StorageResponse(
            data=response['Body'].read(),
            cache_info=CacheInfo(
                last_modified=response['LastModified'],
                etag=quoteless_etag,
            )
        )
        duration = (time.time() - a) * 1000

        current_app.logger.info("%s: Took %0.1fms to get %s byte metatile from s3://%s/%s", meta, duration, response['ContentLength'], s3_bucket, s3_key)
        cache.set(meta, result)

        return result
    except botocore.exceptions.ClientError as e:
        error_code = str(e.response.get('Error', {}).get('Code'))
        if error_code == '304':
            raise MetatileNotModifiedException()
        elif error_code == 'NoSuchKey':
            raise MetatileNotFoundException(
                "No tile found at s3://%s/%s" % (s3_bucket, s3_key)
            )
        else:
            raise UnknownMetatileException(
                "%s at s3://%s/%s" % (error_code,  s3_bucket, s3_key)
            )


def parse_header_time(tstamp):
    if tstamp:
        return dateutil.parser.parse(tstamp)
    else:
        return None


def extract_tile(metatile_bytes, offset):
    data = BytesIO(metatile_bytes)
    z = zipfile.ZipFile(data, 'r')

    offset_key = '{zoom}/{x}/{y}.{fmt}'.format(
        zoom=offset.z,
        x=offset.x,
        y=offset.y,
        fmt=offset.format,
    )

    try:
        return z.read(offset_key)
    except KeyError as e:
        raise TileNotFoundInMetatile(e)


def retrieve_tile(meta, offset, cache_info):
    metatile_data = metatile_fetch(meta, cache_info)
    tile_data = extract_tile(metatile_data.data, offset)

    return StorageResponse(
        data=tile_data,
        cache_info=CacheInfo(
            last_modified=metatile_data.cache_info.last_modified,
            etag=metatile_data.cache_info.etag,
        )
    )


def is_valid_tile_request(z, x, y):
    return (0 <= z < 17) and (0 <= x < 2**z) and (0 <= y < 2**z)


@tile_bp.route('/tilezen/vector/v1/<int:tile_pixel_size>/all/<int:z>/<int:x>/<int:y>.<fmt>')
@tile_bp.route('/tilezen/vector/v1/all/<int:z>/<int:x>/<int:y>.<fmt>')
def handle_tile(z, x, y, fmt, tile_pixel_size=None):
    if not is_valid_tile_request(z, x, y):
        return abort(400, "Requested tile out of range.")

    tile_pixel_size = tile_pixel_size or 256
    tile_size = tile_pixel_size / 256
    if tile_size != int(tile_size):
        return abort(400, "Invalid tile size. %s is not a multiple of 256." % tile_pixel_size)

    requested_tile = TileRequest(z, x, y, fmt)

    tile_size = int(tile_size)

    meta, offset = meta_and_offset(
        requested_tile,
        current_app.config.get('METATILE_SIZE'),
        tile_size,
        metatile_max_detail_zoom=current_app.config.get('METATILE_MAX_DETAIL_ZOOM'),
    )

    request_cache_info = CacheInfo(
        last_modified=parse_header_time(request.headers.get('If-Modified-Since')),
        etag=request.headers.get('If-None-Match'),
    )

    try:
        storage_result = retrieve_tile(meta, offset, request_cache_info)

        response = make_response(storage_result.data)
        response.content_type = MIME_TYPES.get(fmt)
        response.last_modified = storage_result.cache_info.last_modified
        response.cache_control.public = True
        response.cache_control.max_age = current_app.config.get("CACHE_MAX_AGE")
        if current_app.config.get("SHARED_CACHE_MAX_AGE"):
            response.cache_control.s_maxage = current_app.config.get("SHARED_CACHE_MAX_AGE")
        response.set_etag(storage_result.cache_info.etag)
        return response

    except MetatileNotFoundException:
        current_app.logger.exception("Could not find metatile")
        return "Metatile not found", 404
    except TileNotFoundInMetatile:
        current_app.logger.exception("Could not find tile in metatile")
        return "Tile not found", 404
    except MetatileNotModifiedException:
        return "", 304
    except UnknownMetatileException:
        current_app.logger.exception("Error fetching metatile")
        return "Metatile fetch problem", 500


@tile_bp.route('/tilezen/vector/v1/<int:tile_pixel_size>/all/tilejson.<fmt>.json')
@tile_bp.route('/tilezen/vector/v1/all/tilejson.<fmt>.json')
def tilejson(fmt, tile_pixel_size=None):
    tile_size_url_part = ''

    if tile_pixel_size and (tile_pixel_size % 256 != 0):
        return abort(400, "Invalid tile size. %s is not a multiple of 256." % tile_pixel_size)

    if tile_pixel_size:
        tile_size_url_part = '/%s' % tile_pixel_size

    if fmt not in MIME_TYPES:
        return abort(400, "Invalid tile format. Pick one of %s." % MIME_TYPES.keys())

    rendered_template = render_template(
        'tilejson.json',
        tile_size_url_part=tile_size_url_part,
        fmt=fmt,
    )

    resp = make_response(rendered_template)
    resp.headers = {'Content-Type': 'application/json'}
    return resp


@tile_bp.route('/health_check')
def health_check():
    handle_tile(0, 0, 0, 'mvt', tile_pixel_size=256)
    return 'OK'


@tile_bp.route('/preview.html')
def preview_html():
    return render_template(
        'preview.html',
    )
