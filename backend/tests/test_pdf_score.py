import unittest

from app.services.pdf_score import Glyph, PageInk, read_time_signatures
from app.services.score_vision import Staff


def glyph(name: str, x: float, y: float) -> Glyph:
    return Glyph(
        name=name,
        x=x,
        y=y,
        x0=x,
        y0=y - 4,
        x1=x + 6,
        y1=y + 4,
        size=12,
    )


class MeterReadingTests(unittest.TestCase):
    def test_reads_pickup_meter_and_later_change(self):
        staff = Staff(
            line_ys=[100, 110, 120, 130, 140],
            x_left=20,
            x_right=500,
            header_end=50,
        )
        ink = PageInk(
            glyphs=[
                glyph('timeSig2', 60, 110),
                glyph('timeSig4', 60, 130),
                glyph('timeSig3', 180, 110),
                glyph('timeSig4', 180, 130),
            ]
        )

        self.assertEqual(
            read_time_signatures(ink, staff),
            [(60, (2, 4)), (180, (3, 4))],
        )
        self.assertEqual(staff.header_end, 66)


if __name__ == '__main__':
    unittest.main()
