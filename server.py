import boto3
import botocore
import dateutil.parser
import hashlib
import math
import zipfile
from cachetools import LFUCache, cached
from collections import namedtuple
from io import BytesIO
from flask import Flask, current_app, make_response, render_template, request, abort
from flask_compress import Compress
from flask_cors import CORS


app = Flask(__name__)
app.config.from_object('config')
CORS(app)
Compress(app)


MIME_TYPES = {
    "json": "application/json",
    "mvt": "application/x-protobuf",
    "mvtb": "application/x-protobuf",
    "topojson": "application/json",
}
TileRequest = namedtuple('TileRequest', ['z', 'x', 'y', 'format'])
CacheInfo = namedtuple('CacheInfo', ['last_modified', 'etag'])
StorageResponse = namedtuple('StorageResponse', ['data', 'cache_info'])
lfu_cache = LFUCache(50)


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

    if requested_tile.z < delta_z:
        meta = TileRequest(0, 0, 0, 'zip')
        offset = TileRequest(0, 0, 0, requested_tile.format)
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
        offset = TileRequest(
            requested_tile.z - meta.z,
            requested_tile.x - (meta.x << delta_z),
            requested_tile.y - (meta.y << delta_z),
            requested_tile.format,
        )

    return meta, offset


def compute_key(prefix, layer, meta_tile, include_hash=True):
    k = "/{layer}/{z}/{x}/{y}.{fmt}".format(
        layer=layer,
        z=meta_tile.z,
        x=meta_tile.x,
        y=meta_tile.y,
        fmt=meta_tile.format,
    )

    if include_hash:
        h = hashlib.md5(k.encode('utf8')).hexdigest()[:5]
        k = "/{hash}{suffix}".format(
            hash=h,
            suffix=k,
        )

    if prefix:
        k = "/{prefix}{suffix}".format(
            prefix=prefix,
            suffix=k,
        )

    # Strip off the leading slash
    return k[1:]


@cached(lfu_cache)
def metatile_fetch(meta, cache_info):
    s3_key_prefix = current_app.config.get('S3_PREFIX')
    include_hash = current_app.config.get('INCLUDE_HASH')
    requester_pays = current_app.config.get('REQUESTER_PAYS')

    s3_bucket = current_app.config.get('S3_BUCKET')
    s3_key = compute_key(s3_key_prefix, 'all', meta, include_hash)

    s3 = boto3.client('s3')
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
        response = s3.get_object(**get_params)

        # Strip the quotes that boto includes
        quoteless_etag = response['ETag'][1:-1]
        result = StorageResponse(
            data=response['Body'].read(),
            cache_info=CacheInfo(
                last_modified=response['LastModified'],
                etag=quoteless_etag,
            )
        )

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


@cached(lfu_cache)
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


@app.route('/tilezen/vector/v1/<int:tile_pixel_size>/all/<int:z>/<int:x>/<int:y>.<fmt>')
def handle_tile(tile_pixel_size, z, x, y, fmt):
    requested_tile = TileRequest(z, x, y, fmt)

    tile_size = tile_pixel_size / 256
    if tile_size != int(tile_size):
        return abort(400, "Invalid tile size. %s is not a multiple of 256." % tile_pixel_size)

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


@app.route('/preview.html')
def preview_html():
    return render_template(
        'preview.html',
    )
