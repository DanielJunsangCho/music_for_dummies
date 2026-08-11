"""Draw what the vision engine sees on top of a rendered page.

Usage: python tools/debug_vision.py <pdf> <page> [out.png]
"""
import sys
import os

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import score_vision as sv  # noqa: E402

STAFF = (255, 170, 60)
MEASURE = (80, 200, 255)
FILLED = (60, 220, 90)
HOLLOW = (255, 120, 220)


def main() -> None:
    pdf = sys.argv[1]
    page = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    out = sys.argv[3] if len(sys.argv) > 3 else '/tmp/debug_vision.png'

    import fitz

    doc = fitz.open(pdf)
    geo, gray = sv.read_page(doc[page - 1])
    canvas = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    canvas = (canvas * 0.45 + 255 * 0.55).astype(np.uint8)

    for system in geo.systems:
        for staff in system.staves:
            for y in staff.line_ys:
                cv2.line(canvas, (int(staff.x_left), int(y)),
                         (int(staff.x_right), int(y)), STAFF, 1)
            cv2.line(canvas, (int(staff.header_end), int(staff.top) - 20),
                     (int(staff.header_end), int(staff.bottom) + 20), (200, 0, 200), 2)
        cv2.putText(canvas, f'S{system.index} {system.staves[0].clef}'
                    f' {system.staves[0].key_sharps:+d}',
                    (int(system.x_left) - 10, int(system.top) - 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (150, 60, 200), 2)

    for m in geo.measures:
        cv2.rectangle(canvas, (int(m.x1), int(m.top) - 8), (int(m.x2), int(m.bottom) + 8),
                      MEASURE, 2)
        cv2.putText(canvas, str(m.index + 1), (int(m.x1) + 6, int(m.top) - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 120, 200), 2)

    for n in geo.noteheads:
        color = FILLED if n.filled else HOLLOW
        cv2.rectangle(canvas, (int(n.x1), int(n.y1)), (int(n.x2), int(n.y2)), color, 2)
        cv2.putText(canvas, n.name, (int(n.x1) - 4, int(n.y1) - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1, cv2.LINE_AA)

    cv2.imwrite(out, canvas)
    print(f'{out}  source={geo.source} systems={len(geo.systems)} '
          f'measures={len(geo.measures)} notes={len(geo.noteheads)} '
          f'space={geo.space:.1f} time={geo.time_signature}')


if __name__ == '__main__':
    main()
