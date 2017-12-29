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

    def test_compute_key(self):
        from server import compute_key

        t = TileRequest(13, 4008, 3973, 'zip')

        self.assertEquals(
            'abc/c1315/all/13/4008/3973.zip',
            compute_key('abc', 'all', t, True))
        self.assertEquals(
            'c1315/all/13/4008/3973.zip',
            compute_key('', 'all', t, True))
        self.assertEquals(
            'all/13/4008/3973.zip',
            compute_key('', 'all', t, False))


class HandleTileTestCase(unittest.TestCase):
    def test_handle_tile_storage_hit(self):
        pass


if __name__ == '__main__':
    unittest.main()
