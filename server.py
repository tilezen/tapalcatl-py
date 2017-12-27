import boto3
import botocore
import dateutil.parser
import hashlib
import math
import zipfile
from collections import namedtuple
from cStringIO import StringIO
from flask import Flask, current_app, make_response, request
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


def meta_and_offset(requested_tile, meta_size, tile_size):
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
        meta = TileRequest(
            requested_tile.x >> delta_z,
            requested_tile.y >> delta_z,
            requested_tile.z - delta_z,
            'zip',
        )
        offset = TileRequest(
            requested_tile.x - (meta.x << delta_z),
            requested_tile.y - (meta.y << delta_z),
            requested_tile.z - meta.z,
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
        h = hashlib.md5(k).hexdigest()[:5]
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


def metatile_fetch(meta, last_modified):
    s3_key_prefix = current_app.config.get('S3_PREFIX')
    include_hash = current_app.config.get('INCLUDE_HASH')

    s3_bucket = current_app.config.get('S3_BUCKET')
    s3_key = compute_key(s3_key_prefix, 'all', meta, include_hash)

    current_app.logger.info("Fetching s3://%s/%s", s3_bucket, s3_key)

    s3 = boto3.client('s3')
    get_params = {
        "Bucket": s3_bucket,
        "Key": s3_key,
    }

    if last_modified:
        get_params['IfModifiedSince'] = last_modified

    try:
        return s3.get_object(**get_params)
    except botocore.exceptions.ClientError as e:
        error_code = str(e.response.get('Error', {}).get('Code'))
        if error_code == '304':
            raise MetatileNotModifiedException()
        elif error_code == 'NoSuchKey':
            raise MetatileNotFoundException("s3://%s/%s" % (s3_bucket, s3_key))
        else:
            raise UnknownMetatileException(error_code)


def parse_header_time(tstamp):
    if tstamp:
        return dateutil.parser.parse(tstamp)
    else:
        return None


def extract_tile(data, offset):
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

@app.route('/mapzen/vector/v1/<int:tile_pixel_size>/all/<int:z>/<int:x>/<int:y>.<fmt>')
def handle_tile(tile_pixel_size, z, x, y, fmt):
    requested_tile = TileRequest(x, y, z, fmt)

    tile_size = tile_pixel_size / 256

    meta, offset = meta_and_offset(
        requested_tile,
        current_app.config.get('METATILE_SIZE'),
        tile_size,
    )

    request_last_mod = parse_header_time(request.headers.get('If-Modified-Since'))

    try:
        storage_result = metatile_fetch(meta, request_last_mod)

        metatile_data = StringIO(storage_result['Body'].read())
        tile_data = extract_tile(metatile_data, offset)

        response = make_response(tile_data)
        response.headers['Content-Type'] = MIME_TYPES.get(fmt)
        response.headers['Last-Modified'] = storage_result['LastModified']
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
