import unittest
from types import SimpleNamespace

from app.services.score_vision import _full_page_images, _native_scale, _sharps_for_key


class FakePage:
    def __init__(self, width, height, images, drawings=None):
        self.rect = SimpleNamespace(width=width, height=height)
        self._images = images
        self._drawings = drawings or []

    def get_drawings(self):
        return self._drawings

    def get_image_info(self, xrefs=True):
        return self._images

    def get_images(self, full=True):
        # xref, smask, width, height, bpc, colorspace, ...
        return [(1, 0, img['width'], img['height'], 8, 'DeviceGray') for img in self._images]


class NativeScaleTests(unittest.TestCase):
    def test_duplicate_full_page_images_use_largest(self):
        page = FakePage(115, 157, [
            {'bbox': (0, 0, 115, 157), 'width': 318, 'height': 434, 'xref': 1},
            {'bbox': (0, 0, 115, 157), 'width': 956, 'height': 1305, 'xref': 2},
        ])
        self.assertEqual(len(_full_page_images(page)), 2)
        self.assertAlmostEqual(_native_scale(page), 956 / 115, places=3)

    def test_vector_art_is_not_treated_as_a_scan(self):
        page = FakePage(500, 700, [
            {'bbox': (0, 0, 500, 700), 'width': 1000, 'height': 1400, 'xref': 1},
        ], drawings=[{'items': []}])
        self.assertIsNone(_native_scale(page))


class SharpsForKeyTests(unittest.TestCase):
    def test_common_signatures(self):
        self.assertEqual(_sharps_for_key(0, 'major'), 0)   # C
        self.assertEqual(_sharps_for_key(7, 'major'), 1)   # G
        self.assertEqual(_sharps_for_key(2, 'minor'), -1)  # D minor -> 1 flat
        self.assertEqual(_sharps_for_key(9, 'minor'), 0)   # A minor


if __name__ == '__main__':
    unittest.main()
