import unittest
from server import TileRequest


class MetatileTestCase(unittest.TestCase):
    def assertTileEquals(self, expected, actual):
        self.assertEquals(expected.z, actual.z)
        self.assertEquals(expected.x, actual.x)
        self.assertEquals(expected.y, actual.y)
        self.assertEquals(expected.format, actual.format)

    def test_is_power_of_two(self):
        from server import is_power_of_two

        self.assertTrue(is_power_of_two(1))
        self.assertTrue(is_power_of_two(2))
        self.assertTrue(is_power_of_two(4))
        self.assertTrue(is_power_of_two(8))

        self.assertFalse(is_power_of_two(3))
        self.assertFalse(is_power_of_two(5))
        self.assertFalse(is_power_of_two(-1))

    def test_size_to_zoom(self):
        from server import size_to_zoom

        self.assertEquals(0.0, size_to_zoom(1))
        self.assertEquals(1.0, size_to_zoom(2))
        self.assertEquals(2.0, size_to_zoom(4))

    def test_meta_and_offset(self):
        from server import meta_and_offset

        meta, offset = meta_and_offset(TileRequest(0, 0, 0, 'json'), 1, 1)
        self.assertTileEquals(TileRequest(0, 0, 0, 'zip'), meta)
        self.assertTileEquals(TileRequest(0, 0, 0, 'json'), offset)

        meta, offset = meta_and_offset(TileRequest(12, 637, 936, 'json'), 1, 1)
        self.assertTileEquals(TileRequest(12, 637, 936, 'zip'), meta)
        self.assertTileEquals(TileRequest(0, 0, 0, 'json'), offset)

        meta, offset = meta_and_offset(TileRequest(12, 637, 936, 'json'), 2, 1)
        self.assertTileEquals(TileRequest(11, 318, 468, 'zip'), meta)
        self.assertTileEquals(TileRequest(1, 1, 0, 'json'), offset)

        meta, offset = meta_and_offset(TileRequest(12, 637, 936, 'json'), 2, 2)
        self.assertTileEquals(TileRequest(12, 637, 936, 'zip'), meta)
        self.assertTileEquals(TileRequest(0, 0, 0, 'json'), offset)

        meta, offset = meta_and_offset(TileRequest(12, 637, 935, 'json'), 8, 1)
        self.assertTileEquals(TileRequest(9, 79, 116, 'zip'), meta)
        self.assertTileEquals(TileRequest(3, 5, 7, 'json'), offset)

        # check that the "512px" 0/0/0 tile is accessible.
        meta, offset = meta_and_offset(TileRequest(0, 0, 0, 'json'), 2, 2)
        self.assertTileEquals(TileRequest(0, 0, 0, 'zip'), meta)
        self.assertTileEquals(TileRequest(0, 0, 0, 'json'), offset)

        # check that when the metatile would be smaller than the world (i.e:
        # zoom < 0) then it just stops at 0 and we get the offset to the 0/0/0
        # tile.
        meta, offset = meta_and_offset(TileRequest(0, 0, 0, 'json'), 2, 1)
        self.assertTileEquals(TileRequest(0, 0, 0, 'zip'), meta)
        self.assertTileEquals(TileRequest(0, 0, 0, 'json'), offset)

    def test_max_detail_zoom(self):
        from server import meta_and_offset

        def check_overzoom(request, meta_z, offset_z):
            tile_px, request_z = map(int, request.split("/"))
            tile_size = tile_px // 256
            meta, offset = meta_and_offset(
                TileRequest(request_z, 0, 0, 'json'), 4, tile_size,
                metatile_max_detail_zoom=14)
            self.assertTileEquals(TileRequest(meta_z, 0, 0, 'zip'), meta)
            self.assertTileEquals(TileRequest(offset_z, 0, 0, 'json'), offset)

        # check that when the requested tile is past the max level of detail,
        # then it falls back to "smaller" tiles.
        #
        # base tile:
        check_overzoom("1024/14", meta_z=14, offset_z=0)

        # first fallback level, actually returning a "512px" tile, rather than
        # the requested "1024px", but it's at the max detail level, so the
        # content is the same.
        check_overzoom("1024/15", meta_z=14, offset_z=1)

        # second fallback level, actually returning a "256px" tile.
        check_overzoom("1024/16", meta_z=14, offset_z=2)

        # returning a "256px" tile for a "512px" request at the maximum
        # detail level.
        check_overzoom("512/16", meta_z=14, offset_z=2)

        # there is no third level of fallback (with the metatile size tested
        # here, at least), so it should clamp to the minimum tile size. this
        # will probably result in a 404 anyway.
        check_overzoom("1024/17", meta_z=15, offset_z=2)

        # check that passing None (the default) as the max detail zoom
        # disables this behaviour.
        meta, offset = meta_and_offset(TileRequest(16, 0, 0, 'json'), 4, 4)
        self.assertTileEquals(TileRequest(16, 0, 0, 'zip'), meta)
        self.assertTileEquals(TileRequest(0, 0, 0, 'json'), offset)

    def test_zoom_zero(self):
        from server import meta_and_offset

        # check that when the metatile size is larger (e.g: 8), we can still
        # access the low zoom tiles 0-3.
        meta, offset = meta_and_offset(TileRequest(0, 0, 0, 'json'), 8, 2)
        self.assertTileEquals(TileRequest(0, 0, 0, 'zip'), meta)
        self.assertTileEquals(TileRequest(0, 0, 0, 'json'), offset)

        meta, offset = meta_and_offset(TileRequest(1, 0, 1, 'json'), 8, 2)
        self.assertTileEquals(TileRequest(0, 0, 0, 'zip'), meta)
        self.assertTileEquals(TileRequest(1, 0, 1, 'json'), offset)

        meta, offset = meta_and_offset(TileRequest(2, 1, 3, 'json'), 8, 2)
        self.assertTileEquals(TileRequest(0, 0, 0, 'zip'), meta)
        self.assertTileEquals(TileRequest(2, 1, 3, 'json'), offset)

        # only once the offset exceeds the metatile size (at the request tile
        # size) does it start to shift down zooms.
        meta, offset = meta_and_offset(TileRequest(3, 2, 7, 'json'), 8, 2)
        self.assertTileEquals(TileRequest(1, 0, 1, 'zip'), meta)
        self.assertTileEquals(TileRequest(2, 2, 3, 'json'), offset)

    def test_compute_key(self):
        from server import compute_key, KeyFormatType

        t = TileRequest(13, 4008, 3973, 'zip')

        self.assertEquals(
            'abc/c1315/all/13/4008/3973.zip',
            compute_key('abc', 'all', t, KeyFormatType.PREFIX_HASH))
        self.assertEquals(
            'c1315/all/13/4008/3973.zip',
            compute_key('', 'all', t, KeyFormatType.PREFIX_HASH))
        self.assertEquals(
            'all/13/4008/3973.zip',
            compute_key('', 'all', t, KeyFormatType.NO_HASH))
        self.assertEquals(
            'c1315/abc/all/13/4008/3973.zip',
            compute_key('abc', 'all', t, KeyFormatType.HASH_PREFIX))


class HandleTileTestCase(unittest.TestCase):
    def test_handle_tile_storage_hit(self):
        pass


if __name__ == '__main__':
    unittest.main()
