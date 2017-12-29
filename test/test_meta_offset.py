import unittest


class MetaOffsetTest(unittest.TestCase):

    def check_meta_offset(
            self, meta_size, tile_size, coord, exp_meta, exp_offset):
        from server import meta_and_offset
        meta, offset = meta_and_offset(coord, meta_size, tile_size)
        self.assertEquals(exp_meta, meta)
        self.assertEquals(exp_offset, offset)

    def test_0(self):
        from server import TileRequest
        self.check_meta_offset(
            1, 1,
            TileRequest(0, 0, 0, "json"),
            TileRequest(0, 0, 0, "zip"),
            TileRequest(0, 0, 0, "json"))

    def test_meta_1(self):
        from server import TileRequest
        self.check_meta_offset(
            1, 1,
            TileRequest(637, 936, 12, "json"),
            TileRequest(637, 936, 12, "zip"),
            TileRequest(0, 0, 0, "json"))

    def test_meta_2(self):
        from server import TileRequest
        self.check_meta_offset(
            2, 1,
            TileRequest(637, 936, 12, "json"),
            TileRequest(318, 468, 11, "zip"),
            TileRequest(1, 0, 1, "json"))

    def test_meta_tile_2(self):
        from server import TileRequest
        self.check_meta_offset(
            2, 2,
            TileRequest(637, 936, 12, "json"),
            TileRequest(637, 936, 12, "zip"),
            TileRequest(0, 0, 0, "json"))

    def test_large_meta(self):
        from server import TileRequest
        self.check_meta_offset(
            8, 1,
            TileRequest(637, 935, 12, "json"),
            TileRequest(79, 116, 9, "zip"),
            TileRequest(5, 7, 3, "json"))

    def test_512_accessible(self):
        # check that the "512px" 0/0/0 tile is accessible.
        from server import TileRequest
        self.check_meta_offset(
            2, 2,
            TileRequest(0, 0, 0, "json"),
            TileRequest(0, 0, 0, "zip"),
            TileRequest(0, 0, 0, "json"))

    def test_meta_stops_0(self):
        # check that when the metatile would be smaller than the world (i.e:
        # zoom < 0) then it just stops at 0 and we get the offset to the 0/0/0
        # tile.
        from server import TileRequest
        self.check_meta_offset(
            2, 1,
            TileRequest(0, 0, 0, "json"),
            TileRequest(0, 0, 0, "zip"),
            TileRequest(0, 0, 0, "json"))


if __name__ == '__main__':
    unittest.main()
