"""
Deterministic score-vision engine.

Reads engraved sheet music (scanned or rendered) and recovers exact page
geometry: staff lines, systems, barlines, measures and noteheads, plus the
pitch of each notehead from its staff position, clef, key signature and
accidentals.

Unlike a neural OMR pass this is fast (sub-second per page), deterministic,
and - most importantly - every musical object keeps the pixel box it was
found at, so overlays can be anchored to real ink instead of estimated
beat fractions.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

LETTERS = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
LETTER_SEMITONES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

SHARP_ORDER = ['F', 'C', 'G', 'D', 'A', 'E', 'B']
FLAT_ORDER = ['B', 'E', 'A', 'D', 'G', 'C', 'F']

# Canonical staff positions of key-signature accidentals (0 = top line,
# +1 per diatonic step downward), in written order.
KEY_SIG_POSITIONS = {
    ('treble', 'sharp'): [0, 3, -1, 2, 5, 1, 4],
    ('treble', 'flat'): [4, 1, 5, 2, 6, 3, 7],
    ('bass', 'sharp'): [2, 5, 1, 4, 7, 3, 6],
    ('bass', 'flat'): [6, 3, 7, 4, 8, 5, 9],
}

# Note that sits on the top staff line, per clef.
CLEF_TOP_LINE = {'treble': ('F', 5), 'bass': ('A', 3)}


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class Staff:
    line_ys: list
    x_left: float
    x_right: float
    clef: str = 'treble'
    key_sharps: int = 0
    header_end: float = 0.0

    @property
    def space(self) -> float:
        return (self.line_ys[-1] - self.line_ys[0]) / 4.0

    @property
    def top(self) -> float:
        return self.line_ys[0]

    @property
    def bottom(self) -> float:
        return self.line_ys[-1]

    @property
    def y_center(self) -> float:
        return (self.top + self.bottom) / 2.0

    def staff_position(self, y: float) -> int:
        """Diatonic steps below the top line; one step = half a staff space."""
        return int(round((y - self.top) / (self.space / 2.0)))

    def y_of_position(self, position: int) -> float:
        return self.top + position * (self.space / 2.0)


@dataclass
class System:
    staves: list
    index: int = 0

    @property
    def top(self) -> float:
        return min(s.top for s in self.staves)

    @property
    def bottom(self) -> float:
        return max(s.bottom for s in self.staves)

    @property
    def x_left(self) -> float:
        return min(s.x_left for s in self.staves)

    @property
    def x_right(self) -> float:
        return max(s.x_right for s in self.staves)

    @property
    def space(self) -> float:
        return float(np.median([s.space for s in self.staves]))


@dataclass
class Notehead:
    cx: float
    cy: float
    x1: float
    y1: float
    x2: float
    y2: float
    filled: bool
    staff: Staff
    system_index: int
    staff_position: int = 0
    midi: int = 0
    name: str = ''
    measure_index: int = -1
    accidental: Optional[str] = None
    onset_index: int = 0


@dataclass
class Measure:
    system_index: int
    index: int
    x1: float
    x2: float
    top: float
    bottom: float
    noteheads: list = field(default_factory=list)


@dataclass
class PageGeometry:
    width: int
    height: int
    systems: list
    measures: list
    noteheads: list
    space: float
    skew_deg: float = 0.0
    time_signature: Optional[tuple] = None
    # (measure_index, (numerator, denominator)) for each meter change.
    meter_changes: list = field(default_factory=list)
    source: str = 'vision'


class ScoreImage:
    """
    Pre-computed ink layers for one page.

    Staff lines are removed by run length rather than morphology: a pixel on
    a staff line row is erased only when the vertical ink run through it is
    as thin as a staff line. Anything thicker is a glyph crossing the line
    and is kept intact, which avoids both leftover line fragments (they
    weld separate glyphs into one blob) and holes punched through noteheads.
    """

    def __init__(self, gray: np.ndarray):
        self.gray = gray
        self.height, self.width = gray.shape[:2]
        global_bw = binarize(gray)
        self.photo = is_photo_like(gray, global_bw)

        if self.photo:
            # Phone photos: global thresholds flood the page. Use adaptive ink
            # and short horizontal segments that tolerate wavy staff lines.
            self.bw = photo_binarize(gray)
            self.faint = self.bw
            self.line_thickness = estimate_line_thickness(self.bw) or 2.0
            self.space = 18.0  # refined once staves are found
            kern_w = max(20, int(self.width * 0.05))
            self.staff_lines = cv2.morphologyEx(
                self.bw, cv2.MORPH_OPEN,
                cv2.getStructuringElement(cv2.MORPH_RECT, (kern_w, 1)),
            )
        else:
            self.bw = global_bw
            # Engravers often print staff lines much lighter than noteheads, and
            # a threshold tuned to the glyphs loses them. Lines are found on a
            # permissive mask; a long horizontal opening rejects the extra noise
            # it picks up.
            self.faint = faint_mask(gray, self.bw)
            white = estimate_staff_space(self.faint) or 17.0
            self.line_thickness = estimate_line_thickness(self.faint) or 3.0
            self.space = white + self.line_thickness
            self.staff_lines = staff_line_mask(self.faint)

        repair = max(5, int(self.line_thickness * 2 + 1))
        self._repair = cv2.getStructuringElement(cv2.MORPH_RECT, (1, repair))
        self.no_staff = cv2.morphologyEx(cv2.subtract(self.bw, self.staff_lines),
                                         cv2.MORPH_CLOSE, self._repair)

    def strip_staff_lines(self, staves: list) -> None:
        """Rebuild `no_staff` precisely once the staff line rows are known."""
        if not staves:
            return
        run_len = _vertical_run_lengths(self.bw)
        max_line = self.line_thickness * 2.2 + 1

        on_line = np.zeros((self.height,), bool)
        reach = int(math.ceil(self.line_thickness * 0.9)) + 1
        for staff in staves:
            for y in staff.line_ys:
                lo = max(0, int(round(y)) - reach)
                hi = min(self.height, int(round(y)) + reach + 1)
                on_line[lo:hi] = True

        removed = ((run_len > 0) & (run_len <= max_line) & on_line[:, None])
        stripped = self.bw.copy()
        stripped[removed] = 0

        # Reconnect strokes only across the rows we erased. A blanket closing
        # would also seal the hole in a half note and make it look filled.
        closed = cv2.morphologyEx(stripped, cv2.MORPH_CLOSE, self._repair)
        zone = cv2.dilate(removed.astype(np.uint8),
                          cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3)))
        self.no_staff = np.maximum(stripped, closed * zone)


def _vertical_run_lengths(bw: np.ndarray) -> np.ndarray:
    """Length of the vertical ink run each pixel belongs to."""
    h = bw.shape[0]
    up = np.zeros(bw.shape, np.int32)
    up[0] = bw[0]
    for y in range(1, h):
        up[y] = (up[y - 1] + 1) * bw[y]
    down = np.zeros(bw.shape, np.int32)
    down[h - 1] = bw[h - 1]
    for y in range(h - 2, -1, -1):
        down[y] = (down[y + 1] + 1) * bw[y]
    return (up + down - 1) * bw


# --------------------------------------------------------------------------
# Low level image ops
# --------------------------------------------------------------------------

def binarize(gray: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    thr, _ = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thr = min(max(float(thr), 110.0), 200.0)
    return (gray < thr).astype(np.uint8)


def faint_mask(gray: np.ndarray, bw: np.ndarray) -> np.ndarray:
    """Everything meaningfully darker than the paper, including hairlines."""
    paper = float(np.percentile(gray, 92))
    thr = max(120.0, paper - max(28.0, paper * 0.14))
    return np.maximum(bw, (gray < thr).astype(np.uint8))


def is_photo_like(gray: np.ndarray, bw: np.ndarray) -> bool:
    """
    Phone photos of scores have uneven lighting and mid-grey paper, so the
    global Otsu/faint masks paint most of the page as ink. Clean flatbed
    scans stay well below these fractions.
    """
    faint = faint_mask(gray, bw)
    return float(bw.mean()) > 0.22 or float(faint.mean()) > 0.35


def photo_binarize(gray: np.ndarray) -> np.ndarray:
    """
    Locally adaptive ink mask for wrinkled, glare-lit phone photos.

    CLAHE equalises page lighting; adaptive threshold then keeps thin staff
    lines and noteheads without claiming the whole shadowed page as ink.
    """
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(16, 16))
    equalized = clahe.apply(gray)
    adaptive = cv2.adaptiveThreshold(
        equalized, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
        51, 12,
    )
    return (adaptive > 0).astype(np.uint8)


def _vertical_runs(bw: np.ndarray, want_ink: bool, lo: int, hi: int) -> list:
    h, w = bw.shape
    runs = []
    for x in range(0, w, max(1, w // 300)):
        col = bw[:, x] > 0
        edges = np.flatnonzero(np.diff(col.astype(np.int8)))
        if len(edges) < 3:
            continue
        starts = np.concatenate(([0], edges + 1))
        ends = np.concatenate((edges + 1, [h]))
        for s, e in zip(starts, ends):
            if bool(col[s]) is want_ink:
                run = e - s
                if lo <= run <= hi:
                    runs.append(run)
    return runs


def _mode(values: list) -> Optional[float]:
    if not values:
        return None
    vals, counts = np.unique(values, return_counts=True)
    return float(vals[np.argmax(counts)])


def estimate_staff_space(bw: np.ndarray) -> Optional[float]:
    return _mode(_vertical_runs(bw, want_ink=False, lo=3, hi=60))


def estimate_line_thickness(bw: np.ndarray) -> Optional[float]:
    return _mode(_vertical_runs(bw, want_ink=True, lo=1, hi=12))


def staff_line_mask(bw: np.ndarray) -> np.ndarray:
    w = bw.shape[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w // 14), 1))
    return cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)


def _rotate(img: np.ndarray, angle_deg: float, cubic: bool = False) -> np.ndarray:
    if abs(angle_deg) < 1e-3:
        return img
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle_deg, 1.0)
    return cv2.warpAffine(img, m, (w, h),
                          flags=cv2.INTER_CUBIC if cubic else cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE if cubic else cv2.BORDER_CONSTANT,
                          borderValue=0)


def deskew(gray: np.ndarray) -> tuple:
    """Rotate so staff lines are horizontal, found by maximising projection peakiness."""
    bw = binarize(gray)
    lines = staff_line_mask(faint_mask(gray, bw))
    small = cv2.resize(lines, None, fx=0.35, fy=0.35, interpolation=cv2.INTER_AREA)

    best_angle, best_score = 0.0, -1.0
    for angle in np.arange(-1.6, 1.61, 0.1):
        proj = _rotate(small, float(angle)).sum(axis=1).astype(np.float64)
        score = float(np.var(proj))
        if score > best_score:
            best_score, best_angle = score, float(angle)
    if abs(best_angle) < 0.05:
        return gray, 0.0
    return _rotate(gray, best_angle, cubic=True), best_angle


MAX_PIXELS = 42_000_000


def _rasterize(page, scale: float) -> np.ndarray:
    import fitz

    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    buf = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n >= 3:
        return cv2.cvtColor(buf[:, :, :3], cv2.COLOR_RGB2GRAY)
    return buf[:, :, 0].copy()


def _full_page_images(page) -> list:
    """
    Embedded images that cover almost the whole page.

    Scanned scores often store the same plate twice (or a low-res preview
    under a high-res plate). Those still count as scans: there is no vector
    music to re-render, only pixels.
    """
    if page.rect.width <= 0 or page.rect.height <= 0:
        return []
    page_area = float(page.rect.width * page.rect.height)
    covers = []
    for info in page.get_image_info(xrefs=True):
        bbox = info.get('bbox')
        width = int(info.get('width') or 0)
        height = int(info.get('height') or 0)
        if not bbox or width <= 0 or height <= 0:
            continue
        x0, y0, x1, y1 = bbox
        area = max(0.0, float(x1 - x0)) * max(0.0, float(y1 - y0))
        if area >= page_area * 0.80:
            covers.append(info)
    return covers


def _native_scale(page) -> Optional[float]:
    """
    For a scanned page (full-page image, no vector art), the scale that
    renders it at the embedded image's own resolution. Rendering above that
    only upsamples and costs time.
    """
    if page.get_drawings():
        return None
    covers = _full_page_images(page)
    if not covers:
        images = page.get_images(full=True)
        if len(images) != 1:
            return None
        width = images[0][2]
        if not width or page.rect.width <= 0:
            return None
        return float(width) / float(page.rect.width)

    best = max(covers, key=lambda info: int(info.get('width') or 0) * int(info.get('height') or 0))
    return float(best['width']) / float(page.rect.width)


def _clamp_scale(page, scale: float) -> float:
    while (page.rect.width * scale) * (page.rect.height * scale) > MAX_PIXELS:
        scale *= 0.85
    return min(12.0, max(0.5, scale))


def render_page(page, target_space: float = 18.0) -> tuple:
    """
    Render a page to grayscale at a resolution where staves are measurable.

    Returns the image and the points-to-pixels scale it was rendered at, so
    vector coordinates read from the PDF can be placed on the same image.

    Engraved PDFs are re-rendered from their vector source at the scale we
    need, which stays crisp. Scans are rendered at the resolution they were
    scanned at and then resampled, since there is no more detail to get.
    """
    native = _native_scale(page)

    # Scanned plate: stay at native resolution. Never fall through to the
    # vector path, which will happily undersample a 115-pt page box.
    if native is not None:
        scale = _clamp_scale(page, native)
        gray = _rasterize(page, scale)
        space = estimate_staff_space(faint_mask(gray, binarize(gray)))
        if not space or space <= 0:
            return gray, scale

        ratio = float(target_space) / float(space)
        # Upsampling a scan invents ink; only do a little when the plate is
        # genuinely too small to measure staves.
        if ratio > 1.25 and gray.shape[0] * gray.shape[1] < MAX_PIXELS * 0.35:
            ratio = min(ratio, 2.0)
            if gray.shape[0] * gray.shape[1] * ratio * ratio > MAX_PIXELS:
                ratio = math.sqrt(MAX_PIXELS / float(gray.shape[0] * gray.shape[1]))
            if ratio > 1.05:
                gray = cv2.resize(gray, None, fx=ratio, fy=ratio,
                                  interpolation=cv2.INTER_CUBIC)
                return gray, scale * ratio
        return gray, scale

    # Vector / engraved: probe at a modest scale, then re-render crisply.
    base = 2.0
    gray = _rasterize(page, base)
    space = estimate_staff_space(faint_mask(gray, binarize(gray)))
    if not space or space <= 0:
        return gray, base

    ratio = float(target_space) / float(space)
    if 0.85 <= ratio <= 1.2:
        return gray, base

    scale = _clamp_scale(page, base * ratio)
    crisp = _rasterize(page, scale)
    check = estimate_staff_space(faint_mask(crisp, binarize(crisp)))
    if check and check > 3:
        return crisp, scale
    return gray, base


# --------------------------------------------------------------------------
# Staves and systems
# --------------------------------------------------------------------------

def detect_staves(img: ScoreImage) -> list:
    """Find 5-line staves as evenly spaced peaks of long horizontal ink."""
    if getattr(img, 'photo', False):
        staves = detect_staves_photo(img)
        if staves:
            return staves

    lines = img.staff_lines
    h, w = lines.shape
    proj = lines.sum(axis=1).astype(np.float64)
    if proj.max() <= 0:
        return []

    space = img.space
    min_dist = max(4, int(space * 0.55))
    threshold = max(w * 0.18, proj.max() * 0.22)

    peaks = []
    y = 0
    while y < h:
        if proj[y] >= threshold:
            y2 = y
            while y2 + 1 < h and proj[y2 + 1] >= threshold:
                y2 += 1
            peaks.append(y + int(np.argmax(proj[y:y2 + 1])))
            y = y2 + 1
        else:
            y += 1

    merged = []
    for y in peaks:
        if merged and y - merged[-1] < min_dist:
            if proj[y] > proj[merged[-1]]:
                merged[-1] = y
        else:
            merged.append(y)

    staves = _staves_from_lines(merged, lines, space)
    # Clean scans that still look like photos of wrinkled paper sometimes
    # defeat the global projection; fall back to the photo finder.
    if len(staves) < 2 and not getattr(img, 'photo', False):
        photo_staves = detect_staves_photo(img)
        if len(photo_staves) > len(staves):
            return photo_staves
    return staves


def detect_staves_photo(img: ScoreImage) -> list:
    """
    Recover staves on phone photos where wrinkles break long horizontal runs.

    1. Vote for staff rows in vertical page strips (short kernels tolerate waves).
    2. Locate system bands from the smoothed vote profile.
    3. Inside each band, fit a 5-line staff by projection chaining *and*
       Hough segments, then keep the non-overlapping set.
    """
    segs = img.staff_lines
    h, w = segs.shape
    if h < 40 or w < 40 or segs.mean() <= 0:
        return []

    votes = np.zeros(h, np.float64)
    bands_n = 8
    for band in range(bands_n):
        x1 = int(band * w / bands_n)
        x2 = int((band + 1) * w / bands_n)
        proj = segs[:, x1:x2].sum(axis=1).astype(np.float64)
        band_w = max(1, x2 - x1)
        thr = max(band_w * 0.15, float(np.percentile(proj, 75)) * 0.30)
        votes += np.clip(proj / max(thr, 1.0), 0.0, 3.0)

    page_space = _estimate_space_from_votes(votes)
    img.space = page_space

    system_bands = _system_bands_from_votes(votes, h)
    candidates = []
    for y0, y1 in system_bands:
        chained = _chain_staff_in_band(votes, y0, y1, page_space)
        if chained is not None:
            candidates.append(chained)
        hough = _hough_staff_in_band(segs, y0, y1, page_space)
        if hough is not None:
            candidates.append(hough)
        # Perspective: upper systems can be ~20% smaller than the page median.
        local = page_space * 0.85
        if abs(local - page_space) >= 1.0:
            chained = _chain_staff_in_band(votes, y0, y1, local)
            if chained is not None:
                candidates.append(chained)
            hough = _hough_staff_in_band(segs, y0, y1, local)
            if hough is not None:
                candidates.append(hough)

    chains = _merge_staff_candidates(candidates, page_space)
    staves = []
    for chain in chains:
        x_left, x_right = _staff_extent(segs, chain)
        if x_right - x_left < w * 0.35:
            x_left, x_right = int(w * 0.05), int(w * 0.95)
        staves.append(Staff(
            line_ys=[float(v) for v in chain],
            x_left=float(x_left),
            x_right=float(x_right),
        ))
    if len(staves) >= 2:
        median_space = float(np.median([s.space for s in staves]))
        # Drop compressed false staves once the page's real space is known.
        staves = [s for s in staves if s.space >= median_space * 0.72]
    if staves:
        img.space = float(np.median([s.space for s in staves]))
    return staves


def _estimate_space_from_votes(votes: np.ndarray) -> float:
    peaks = []
    y = 0
    h = len(votes)
    while y < h:
        if votes[y] >= 0.7:
            y2 = y
            while y2 + 1 < h and votes[y2 + 1] >= 0.7:
                y2 += 1
            peaks.append(y + int(np.argmax(votes[y:y2 + 1])))
            y = y2 + 1
        else:
            y += 1
    gaps = np.diff(peaks) if len(peaks) >= 2 else np.array([])
    cand = gaps[(gaps >= 12) & (gaps <= 28)] if len(gaps) else np.array([])
    return float(np.median(cand)) if len(cand) >= 3 else 18.0


def _system_bands_from_votes(votes: np.ndarray, height: int) -> list:
    win = max(40, height // 80)
    smoothed = np.convolve(votes, np.ones(win) / win, mode='same')
    thr = max(1.0, float(np.percentile(smoothed, 65)))
    bands = []
    y = 0
    while y < height:
        if smoothed[y] >= thr:
            y2 = y
            while y2 + 1 < height and smoothed[y2 + 1] >= thr:
                y2 += 1
            if y2 - y >= 24:
                bands.append((y, y2))
            y = y2 + 1
        else:
            y += 1
    out = []
    for y0, y1 in bands:
        if y1 < height * 0.08 or y0 > height * 0.92:
            continue
        if (y1 - y0) > height * 0.14:
            continue
        out.append((y0, y1))
    return out


def _chain_staff_in_band(votes: np.ndarray, y0: int, y1: int,
                         page_space: float) -> Optional[list]:
    h = len(votes)
    a = max(0, y0 - int(page_space))
    b = min(h, y1 + int(page_space))
    local = votes[a:b]
    peaks = []
    y = 0
    while y < len(local):
        if local[y] >= 0.5:
            y2 = y
            while y2 + 1 < len(local) and local[y2 + 1] >= 0.5:
                y2 += 1
            peaks.append(a + y + int(np.argmax(local[y:y2 + 1])))
            y = y2 + 1
        else:
            y += 1
    merged = []
    for peak in peaks:
        if merged and peak - merged[-1] < 3:
            if votes[peak] > votes[merged[-1]]:
                merged[-1] = peak
        else:
            merged.append(peak)
    peaks = merged

    best = None
    best_score = -1.0
    for i in range(len(peaks)):
        for j in range(i + 1, min(i + 7, len(peaks))):
            space = peaks[j] - peaks[i]
            if abs(space - page_space) > page_space * 0.45:
                continue
            if not (10 <= space <= 32):
                continue
            chain = [peaks[i], peaks[j]]
            cursor = j
            ok = True
            for _ in range(3):
                target = chain[-1] + space
                best_peak = None
                best_dist = 1e9
                best_k = None
                for k in range(cursor + 1, min(cursor + 7, len(peaks))):
                    dist = abs(peaks[k] - target)
                    if dist < best_dist:
                        best_dist = dist
                        best_peak = peaks[k]
                        best_k = k
                if best_peak is None or best_dist > max(5.5, space * 0.45):
                    ok = False
                    break
                chain.append(best_peak)
                cursor = best_k
            if not ok:
                continue
            gaps = np.diff(chain).astype(np.float64)
            score = float(np.mean([votes[yy] for yy in chain])) / (1.0 + float(np.std(gaps)))
            if score > best_score:
                best_score = score
                best = chain
    if best is None or best_score < 0.9:
        return None
    return [float(v) for v in best]


def _hough_staff_in_band(segs: np.ndarray, y0: int, y1: int,
                         page_space: float) -> Optional[list]:
    h, w = segs.shape
    a = max(0, y0 - 15)
    b = min(h, y1 + 15)
    band = (segs[a:b] * 255).astype(np.uint8)
    min_len = max(30, w // 16)
    lines = cv2.HoughLinesP(
        band, 1, np.pi / 180,
        threshold=max(20, min_len // 4),
        minLineLength=min_len,
        maxLineGap=30,
    )
    if lines is None:
        return None

    ys = []
    for x1, yy1, x2, yy2 in lines[:, 0]:
        if abs(int(yy2) - int(yy1)) > abs(int(x2) - int(x1)) * 0.12:
            continue
        ys.append(a + 0.5 * (float(yy1) + float(yy2)))
    if len(ys) < 5:
        return None

    ys = np.sort(np.asarray(ys, dtype=np.float64))
    clusters = []
    for y in ys:
        if not clusters or abs(y - float(np.mean(clusters[-1]))) > page_space * 0.35:
            clusters.append([float(y)])
        else:
            clusters[-1].append(float(y))
    centers = [float(np.median(cluster)) for cluster in clusters]
    if len(centers) < 5:
        return None

    best = None
    best_err = 1e9
    target = page_space if page_space >= 10 else 16.0
    for i in range(len(centers) - 4):
        window = centers[i:i + 5]
        gaps = np.diff(window)
        med = float(np.median(gaps))
        if med < 10.0 or med > 30.0:
            continue
        if not np.all((gaps > 8.0) & (gaps < 34.0)):
            continue
        err = float(np.mean(np.abs(gaps - target)) + np.std(gaps))
        if err < best_err:
            best_err = err
            best = window
    return best


def _merge_staff_candidates(candidates: list, page_space: float) -> list:
    """Keep one staff per vertical region; tolerate mild perspective shrink."""
    scored = []
    for staff in candidates:
        if not staff or len(staff) != 5:
            continue
        gaps = np.diff(staff).astype(np.float64)
        med = float(np.median(gaps))
        if med < 10.0 or med > 30.0:
            continue
        # Allow smaller upper systems; reject only extreme half-space junk
        # when the page median is clearly larger.
        if page_space >= 15 and med < page_space * 0.55:
            continue
        if float(np.std(gaps)) > max(4.2, med * 0.32):
            continue
        score = -float(np.std(gaps))
        scored.append((score, [float(v) for v in staff]))
    scored.sort(reverse=True, key=lambda item: item[0])

    selected = []
    for _, staff in scored:
        center = 0.5 * (staff[0] + staff[-1])
        height = staff[-1] - staff[0]
        if any(abs(center - 0.5 * (other[0] + other[-1])) < height * 0.55
               for other in selected):
            continue
        selected.append(staff)
    selected.sort(key=lambda staff: staff[0])
    return selected


def _staves_from_lines(line_ys: list, lines_mask: np.ndarray, space: float) -> list:
    """
    Group detected lines into evenly spaced runs, then keep the runs of five.

    Guitar scores print a 6-line tablature staff under the notation. Taking
    any five consecutive lines would carve bogus staves out of the tab, so
    runs are built first and then filtered by line count.
    """
    if len(line_ys) < 5:
        return []

    runs = []
    current = [line_ys[0]]
    for y in line_ys[1:]:
        gap = y - current[-1]
        if len(current) == 1:
            fits = 0 < gap <= space * 2.4
        else:
            median_gap = float(np.median(np.diff(current)))
            fits = abs(gap - median_gap) <= max(3.0, median_gap * 0.35)
        if fits:
            current.append(y)
        else:
            runs.append(current)
            current = [y]
    runs.append(current)

    staves = []
    for run in runs:
        for window in _split_run(run):
            x_left, x_right = _staff_extent(lines_mask, window)
            staves.append(Staff(line_ys=[float(v) for v in window],
                                x_left=float(x_left), x_right=float(x_right)))
    return staves


def _split_run(run: list) -> list:
    """Yield 5-line staves from a run of evenly spaced lines."""
    count = len(run)
    if count == 5:
        return [run]
    # 6 (guitar tab), 4 (bass tab) and other counts are not notation staves.
    if count in (4, 6, 7):
        return []
    if count > 7 and count % 5 == 0:
        return [run[i:i + 5] for i in range(0, count, 5)]
    if count > 7:
        # Best effort: take leading groups of five and drop the remainder.
        return [run[i:i + 5] for i in range(0, count - count % 5, 5)]
    return []


def _staff_extent(lines_mask: np.ndarray, line_ys: list) -> tuple:
    h, w = lines_mask.shape
    y1 = max(0, int(min(line_ys)) - 2)
    y2 = min(h, int(max(line_ys)) + 3)
    cols = np.flatnonzero(lines_mask[y1:y2, :].sum(axis=0) > 0)
    if len(cols) == 0:
        return 0, w - 1
    return int(cols[0]), int(cols[-1])


def group_systems(staves: list, photo: bool = False) -> list:
    """Group staves into systems; braced staves sit closer than system gaps."""
    if not staves:
        return []
    staves = sorted(staves, key=lambda s: s.top)
    if len(staves) == 1:
        return [System(staves=staves, index=0)]

    gaps = [staves[i + 1].top - staves[i].bottom for i in range(len(staves) - 1)]
    median_space = float(np.median([s.space for s in staves]))
    # Phone guitar scores are single-staff systems. A loose threshold merges
    # neighbouring systems on wrinkled pages where vertical gaps compress.
    if photo:
        threshold = median_space * 2.8
    else:
        threshold = min(median_space * 6.0, float(np.median(gaps)) * 0.7)

    systems, current = [], [staves[0]]
    for staff, gap in zip(staves[1:], gaps):
        if gap <= threshold:
            current.append(staff)
        else:
            systems.append(System(staves=current, index=len(systems)))
            current = [staff]
    systems.append(System(staves=current, index=len(systems)))
    return systems


# --------------------------------------------------------------------------
# Glyphs: clef, key signature, accidentals
# --------------------------------------------------------------------------

def _glyph_components(img: ScoreImage, x1, x2, y1, y2, space: float) -> list:
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(img.width, int(x2)), min(img.height, int(y2))
    if x2 <= x1 or y2 <= y1:
        return []
    sub = img.no_staff[y1:y2, x1:x2]
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(sub, 8)
    out = []
    for i in range(1, n):
        x, y, gw, gh, area = stats[i]
        if not (space * 1.1 <= gh <= space * 3.8):
            continue
        if not (space * 0.25 <= gw <= space * 1.6):
            continue
        if area < space * space * 0.15:
            continue
        out.append({
            'x1': x1 + x, 'y1': y1 + y, 'x2': x1 + x + gw, 'y2': y1 + y + gh,
            'cx': x1 + float(centroids[i][0]), 'cy': y1 + float(centroids[i][1]),
            'mask': (labels[y:y + gh, x:x + gw] == i).astype(np.uint8),
        })
    return out


def classify_accidental(glyph: dict) -> Optional[str]:
    """
    Sharp / flat / natural from where the ink sits.

    A flat's loop hangs at the bottom so its top-right is empty; a natural's
    strokes are diagonally offset so top-right and bottom-left are both
    light; a sharp fills all four quadrants.
    """
    mask = glyph['mask']
    h, w = mask.shape
    total = float(mask.sum())
    if h < 3 or w < 3 or total <= 0:
        return None

    mh, mw = h // 2, w // 2
    tl = float(mask[:mh, :mw].sum()) / total
    tr = float(mask[:mh, mw:].sum()) / total
    bl = float(mask[mh:, :mw].sum()) / total
    br = float(mask[mh:, mw:].sum()) / total

    if tr < 0.10 and br > 0.20 and (h / float(w)) > 1.5:
        return 'flat'
    if min(tl, tr, bl, br) > 0.13:
        return 'sharp'
    if tr < 0.17 and bl < 0.17:
        return 'natural'
    return None


def detect_clef(img: ScoreImage, staff: Staff) -> str:
    """Treble clefs overshoot the staff top and bottom; bass clefs do not."""
    space = staff.space
    x1, x2 = int(staff.x_left), int(staff.x_left + space * 4.2)
    y1, y2 = int(staff.top - space * 3.0), int(staff.bottom + space * 3.0)
    x2, y1, y2 = min(x2, img.width), max(0, y1), min(img.height, y2)
    if x2 <= x1 or y2 <= y1:
        return 'treble'
    rows = np.flatnonzero(img.no_staff[y1:y2, x1:x2].sum(axis=1) > 0)
    if len(rows) == 0:
        return 'treble'
    extent = (rows[-1] - rows[0]) / float(staff.bottom - staff.top)
    return 'treble' if extent > 1.25 else 'bass'


def detect_key_signature(img: ScoreImage, staff: Staff) -> tuple:
    """
    Read the key signature after the clef.

    Returns (sharps, header_end_x): sharps is +n sharps / -n flats, and
    header_end_x is where clef+key+time end and music begins.
    """
    space = staff.space
    clef_end = staff.x_left + space * 3.8
    glyphs = _glyph_components(img, clef_end, staff.x_left + space * 15.0,
                               staff.top - space * 2.4, staff.bottom + space * 2.4, space)
    glyphs.sort(key=lambda g: g['cx'])

    run = []
    for g in glyphs:
        kind = classify_accidental(g)
        if kind not in ('sharp', 'flat'):
            continue
        if run and (g['x1'] - run[-1]['x2']) > space * 1.6:
            break
        g['kind'] = kind
        run.append(g)
        if len(run) >= 7:
            break

    if not run:
        return 0, clef_end + space * 2.5

    positions = [staff.staff_position(g['cy']) for g in run]
    count = len(positions)

    def fit_error(kind: str) -> float:
        model = KEY_SIG_POSITIONS.get((staff.clef, kind), [])[:count]
        if len(model) != count:
            return 1e9
        return sum(abs(a - b) for a, b in zip(model, positions)) / float(count)

    votes = sum(1 if g['kind'] == 'sharp' else -1 for g in run)
    sharp_err = fit_error('sharp') - (0.6 if votes > 0 else 0.0)
    flat_err = fit_error('flat') - (0.6 if votes < 0 else 0.0)

    best_err = min(sharp_err, flat_err)
    # Fingerings, string numbers and barre marks often sit where a key
    # signature would, and a bad signature rewrites every pitch on the page.
    # Prefer "no signature" over a fit that does not match the plate.
    if best_err > 0.85:
        return 0, clef_end + space * 2.5

    sharps = count if sharp_err <= flat_err else -count
    return sharps, run[-1]['x2'] + space * 3.0


def read_staff_headers(img: ScoreImage, systems: list) -> None:
    for system in systems:
        for staff in system.staves:
            staff.clef = detect_clef(img, staff)
            staff.key_sharps, staff.header_end = detect_key_signature(img, staff)
    for system in systems:
        if len(system.staves) < 2:
            continue
        winner = Counter(s.key_sharps for s in system.staves).most_common(1)[0][0]
        for staff in system.staves:
            staff.key_sharps = winner

    # A page almost never changes key signature. Treat a reading held by a
    # single system, close to the page consensus, as a miscount.
    readings = Counter(s.key_sharps for sys in systems for s in sys.staves)
    if len(readings) > 1:
        mode, mode_n = readings.most_common(1)[0]
        for system in systems:
            for staff in system.staves:
                if staff.key_sharps == mode:
                    continue
                if readings[staff.key_sharps] < 2 and abs(staff.key_sharps - mode) <= 2:
                    staff.key_sharps = mode


# --------------------------------------------------------------------------
# Noteheads
# --------------------------------------------------------------------------

def _head_size(space: float) -> tuple:
    return max(8, int(round(space * 1.32))), max(6, int(round(space * 1.02)))


def _notehead_templates(space: float) -> list:
    head_w, head_h = _head_size(space)
    templates = []
    for filled in (True, False):
        pad = 3
        tpl = np.zeros((head_h + pad * 2, head_w + pad * 2), np.float32)
        center = (tpl.shape[1] // 2, tpl.shape[0] // 2)
        axes = (head_w // 2, head_h // 2)
        cv2.ellipse(tpl, center, axes, -20, 0, 360, 1.0, -1)
        if not filled:
            shrink = max(2, int(space * 0.22))
            cv2.ellipse(tpl, center,
                        (max(1, axes[0] - shrink), max(1, axes[1] - shrink)),
                        -20, 0, 360, 0.0, -1)
        templates.append((filled, tpl))
    return templates


def _ellipse_masks(space: float):
    head_w, head_h = _head_size(space)
    pad = 3
    shape = (head_h + pad * 2, head_w + pad * 2)
    center = (shape[1] // 2, shape[0] // 2)
    axes = (head_w // 2, head_h // 2)

    outer = np.zeros(shape, np.uint8)
    cv2.ellipse(outer, center, axes, -20, 0, 360, 1, -1)
    shrink = max(2, int(space * 0.26))
    core = np.zeros(shape, np.uint8)
    cv2.ellipse(core, center, (max(1, axes[0] - shrink), max(1, axes[1] - shrink)),
                -20, 0, 360, 1, -1)
    return outer, core, cv2.subtract(outer, core), shape


def _validate_notehead(img: ScoreImage, cand: dict, space: float) -> bool:
    _, core, ring, shape = _ellipse_masks(space)
    hh, hw = shape[0] // 2, shape[1] // 2
    cy, cx = int(round(cand['cy'])), int(round(cand['cx']))
    y1, x1 = cy - hh, cx - hw
    y2, x2 = y1 + shape[0], x1 + shape[1]
    if y1 < 0 or x1 < 0 or y2 > img.height or x2 > img.width:
        return False

    patch = img.no_staff[y1:y2, x1:x2].astype(np.float32)
    core_area, ring_area = float(core.sum()), float(ring.sum())
    if core_area <= 0 or ring_area <= 0:
        return False

    core_fill = float((patch * core).sum()) / core_area
    ring_fill = float((patch * ring).sum()) / ring_area

    if cand['filled']:
        # Rests and flags produce small dense blobs that fill the core but
        # not the ring; a real head fills both almost completely.
        if core_fill < 0.78 or ring_fill < 0.62:
            return False
    elif not (core_fill < 0.62 and ring_fill > 0.70):
        # A ledger line running through a half note intrudes on its hole, so
        # the core test cannot be too strict.
        return False

    if cand['filled']:
        # A beam is thinner than a notehead and far longer. Measuring the ink
        # run through the candidate's centre separates the two cleanly, which
        # a template match alone cannot do at the end of a beam.
        thickness = _run_extent(img.no_staff, cy, cx, axis=0)
        if not (space * 0.68 <= thickness <= space * 2.8):
            return False
        length = _run_extent(img.no_staff, cy, cx, axis=1)
        if length > shape[1] * 2.4:
            return False
    return True


def _run_extent(mask: np.ndarray, y: int, x: int, axis: int) -> int:
    """Length of the contiguous ink run through (y, x) along an axis."""
    if not mask[y, x]:
        return 0
    if axis == 0:
        limit = mask.shape[0]
        lo = y
        while lo > 0 and mask[lo - 1, x]:
            lo -= 1
        hi = y
        while hi < limit - 1 and mask[hi + 1, x]:
            hi += 1
    else:
        limit = mask.shape[1]
        lo = x
        while lo > 0 and mask[y, lo - 1]:
            lo -= 1
        hi = x
        while hi < limit - 1 and mask[y, hi + 1]:
            hi += 1
    return hi - lo + 1


def _ledger_support(img: ScoreImage, staff: Staff, cx: float, position: int) -> bool:
    """
    A note more than one step outside the staff must sit on ledger lines.

    This is what separates real high or low notes from beam stubs, flags and
    other stray ink floating above or below the staff.
    """
    if -1 <= position <= 9:
        return True
    if position <= -2:
        required = position if position % 2 == 0 else position + 1
    else:
        required = position if position % 2 == 0 else position - 1
    if abs(required) > 40:
        return False

    space = staff.space
    head_w, _ = _head_size(space)
    y = staff.y_of_position(required)
    tol = max(2, int(round(img.line_thickness)))
    max_thickness = max(3.0, img.line_thickness * 2.4)

    # Sample where the ledger sticks out past the notehead, on both sides. A
    # beam at the same height is far thicker and stops on one side.
    def side_has_ledger(direction: int) -> bool:
        for frac in (0.58, 0.68, 0.78, 0.88):
            x = int(round(cx + direction * head_w * frac))
            if not (0 <= x < img.width):
                continue
            for dy in range(-tol, tol + 1):
                yy = int(round(y)) + dy
                if not (0 <= yy < img.height) or not img.faint[yy, x]:
                    continue
                if _run_extent(img.faint, yy, x, axis=0) <= max_thickness:
                    return True
        return False

    return side_has_ledger(-1) and side_has_ledger(1)


def detect_noteheads(img: ScoreImage, systems: list) -> list:
    """Template match heads on staff-free ink, then validate by ink distribution."""
    found = []
    for system in systems:
        space = system.space
        top = int(max(0, system.top - space * 5.0))
        bottom = int(min(img.height, system.bottom + space * 5.0))
        if bottom - top < 5:
            continue
        region = img.no_staff[top:bottom, :].astype(np.float32)
        for is_filled, tpl in _notehead_templates(space):
            score = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(score >= (0.55 if is_filled else 0.45))
            for y, x in zip(ys, xs):
                found.append({
                    'cx': float(x + tpl.shape[1] / 2.0),
                    'cy': float(y + tpl.shape[0] / 2.0 + top),
                    'score': float(score[y, x]),
                    'filled': is_filled,
                    'system': system,
                })

    found.sort(key=lambda d: -d['score'])
    kept = []
    for cand in found:
        space = cand['system'].space
        if any(abs(cand['cx'] - k['cx']) < space * 0.9 and abs(cand['cy'] - k['cy']) < space * 0.7
               for k in kept):
            continue
        if _validate_notehead(img, cand, space):
            kept.append(cand)

    noteheads = []
    for cand in kept:
        system = cand['system']
        staff = min(system.staves, key=lambda s: abs(s.y_center - cand['cy']))
        space = staff.space
        if not (staff.top - space * 4.6 <= cand['cy'] <= staff.bottom + space * 4.6):
            continue
        if staff.header_end and cand['cx'] < staff.header_end - space * 0.4:
            continue
        position = staff.staff_position(cand['cy'])
        if not _ledger_support(img, staff, cand['cx'], position):
            continue
        head_w, head_h = _head_size(space)
        noteheads.append(Notehead(
            cx=cand['cx'], cy=cand['cy'],
            x1=cand['cx'] - head_w / 2.0, y1=cand['cy'] - head_h / 2.0,
            x2=cand['cx'] + head_w / 2.0, y2=cand['cy'] + head_h / 2.0,
            filled=cand['filled'], staff=staff, system_index=system.index,
            staff_position=staff.staff_position(cand['cy']),
        ))

    noteheads.sort(key=lambda n: (n.system_index, n.cx, n.cy))
    return noteheads


# --------------------------------------------------------------------------
# Barlines and measures
# --------------------------------------------------------------------------

def detect_barlines(img: ScoreImage, system: System, noteheads: list) -> list:
    """
    Thin vertical strokes spanning exactly the staff height.

    Polyphonic guitar writing has stems that cross the whole staff, so a
    candidate must start at the top line, end at the bottom line without
    overshooting, and carry no notehead (a stem always ends in one).
    """
    results = []
    photo = getattr(img, 'photo', False)
    for staff in system.staves:
        top, bottom = int(max(0, staff.top)), int(min(img.height - 1, staff.bottom))
        if bottom <= top:
            continue
        space = staff.space
        max_width = max(3, int(space * (0.85 if photo else 0.6)))
        overshoot = space * (1.1 if photo else 0.75)
        # Wavy phone photos rarely keep a barline covering 90% of every row.
        min_coverage = 0.72 if photo else 0.90

        band = img.no_staff[top:bottom + 1, :]
        coverage = band.sum(axis=0) / float(band.shape[0])
        xs = np.flatnonzero(coverage >= min_coverage)
        if len(xs) == 0:
            results.append([])
            continue

        clusters, run = [], [int(xs[0])]
        for x in xs[1:]:
            if x - run[-1] <= 2:
                run.append(int(x))
            else:
                clusters.append(run)
                run = [int(x)]
        clusters.append(run)

        staff_notes = [n for n in noteheads if abs(n.staff.y_center - staff.y_center) < space * 0.5]
        mid = (top + bottom) // 2
        bars = []
        for run in clusters:
            if run[-1] - run[0] + 1 > max_width:
                continue
            cx = float(np.mean(run))
            if cx < staff.x_left - space or cx > staff.x_right + space:
                continue
            if staff.header_end and cx < staff.header_end - space * 0.5:
                continue

            col = img.no_staff[:, run[0]:run[-1] + 1].max(axis=1)
            if not col[mid]:
                continue
            y_up = mid
            while y_up > 0 and col[y_up - 1]:
                y_up -= 1
            y_dn = mid
            while y_dn < img.height - 1 and col[y_dn + 1]:
                y_dn += 1

            top_slack = space * (0.65 if photo else 0.4)
            bot_slack = space * (0.65 if photo else 0.4)
            if y_up > top + top_slack or y_dn < bottom - bot_slack:
                continue
            if (top - y_up) > overshoot or (y_dn - bottom) > overshoot:
                continue
            head_clear = space * (0.65 if photo else 0.85)
            if any(abs(n.cx - cx) < head_clear for n in staff_notes):
                continue
            bars.append(cx)
        results.append(bars)

    if not results:
        return []

    if len(results) == 1:
        candidates = results[0]
    else:
        tolerance = system.space * 1.2
        candidates = [x for x in results[0]
                      if all(any(abs(x - o) <= tolerance for o in group) for group in results[1:])]

    merged = []
    for x in sorted(candidates):
        if merged and x - merged[-1] < system.space * 1.5:
            merged[-1] = (merged[-1] + x) / 2.0
        else:
            merged.append(x)
    return merged


def build_measures(img: ScoreImage, systems: list, noteheads: list) -> list:
    measures = []
    index = 0
    for system in systems:
        sys_notes = [n for n in noteheads if n.system_index == system.index]
        bars = detect_barlines(img, system, sys_notes)
        space = system.space
        headers = [s.header_end for s in system.staves if s.header_end]
        left = max(headers) if headers else system.x_left
        right = system.x_right

        bounds = [left] + [b for b in bars if left + space < b < right - space * 0.5] + [right]
        cleaned = [bounds[0]]
        for b in bounds[1:]:
            if b - cleaned[-1] >= space * 3:
                cleaned.append(b)
            else:
                cleaned[-1] = max(cleaned[-1], b)

        pad = space * 2.2
        for i in range(len(cleaned) - 1):
            measures.append(Measure(
                system_index=system.index, index=index,
                x1=float(cleaned[i]), x2=float(cleaned[i + 1]),
                top=float(system.top - pad), bottom=float(system.bottom + pad),
            ))
            index += 1
    return measures


def assign_notes_to_measures(noteheads: list, measures: list) -> None:
    by_system = {}
    for m in measures:
        by_system.setdefault(m.system_index, []).append(m)
    for note in noteheads:
        for measure in by_system.get(note.system_index, []):
            if measure.x1 <= note.cx <= measure.x2:
                note.measure_index = measure.index
                measure.noteheads.append(note)
                break


# --------------------------------------------------------------------------
# Pitch
# --------------------------------------------------------------------------

def _pitch_from_position(position: int, clef: str) -> tuple:
    letter, octave = CLEF_TOP_LINE.get(clef, CLEF_TOP_LINE['treble'])
    idx = LETTERS.index(letter) - position
    return LETTERS[idx % 7], octave + math.floor(idx / 7.0)


def _key_alteration(letter: str, key_sharps: int) -> int:
    if key_sharps > 0 and letter in SHARP_ORDER[:key_sharps]:
        return 1
    if key_sharps < 0 and letter in FLAT_ORDER[:abs(key_sharps)]:
        return -1
    return 0


def apply_pitches(img: ScoreImage, geo: PageGeometry) -> None:
    """Resolve pitches from staff position, clef, key signature and accidentals."""
    for measure in geo.measures:
        active = {}
        for note in sorted(measure.noteheads, key=lambda n: (n.cx, n.cy)):
            staff = note.staff
            space = staff.space
            accidental, best_dx = None, None
            for g in _glyph_components(img,
                                       note.x1 - space * 2.4, note.x1 - space * 0.05,
                                       note.cy - space * 2.0, note.cy + space * 2.0, space):
                # Accidentals are tall; fingering digits and dots are not.
                if (g['y2'] - g['y1']) < space * 1.75:
                    continue
                if abs(g['cy'] - note.cy) > space * 0.55:
                    continue
                dx = note.x1 - g['x2']
                if not (-space * 0.1 <= dx <= space * 1.6):
                    continue
                kind = classify_accidental(g)
                if kind is None:
                    continue
                if best_dx is None or dx < best_dx:
                    best_dx, accidental = dx, kind

            letter, octave = _pitch_from_position(note.staff_position, staff.clef)
            if accidental == 'sharp':
                alter = 1
            elif accidental == 'flat':
                alter = -1
            elif accidental == 'natural':
                alter = 0
            else:
                alter = active.get((letter, octave), _key_alteration(letter, staff.key_sharps))

            if accidental is not None:
                active[(letter, octave)] = alter

            note.accidental = accidental
            note.midi = (octave + 1) * 12 + LETTER_SEMITONES[letter] + alter
            suffix = '#' if alter == 1 else ('b' if alter == -1 else '')
            note.name = f"{letter}{suffix}{octave}"


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------

def read_page(page, target_space: float = 18.0) -> tuple:
    """
    Read one PDF page, preferring the exact route over the inferred one.

    If the publisher left the music font and vector rules in the file we read
    the notation off them directly; that is exact. Otherwise the page is a
    picture of music and we fall back to computer vision.
    """
    from app.services import pdf_score

    gray, scale = render_page(page, target_space)
    if pdf_score.is_engraved(page):
        geo = pdf_score.analyze_page(page, scale)
        if geo is not None and geo.noteheads:
            geo.width, geo.height = gray.shape[1], gray.shape[0]
            geo.source = 'engraved'
            return geo, gray

    geo, deskewed = analyze_page_geometry(gray)
    return geo, deskewed


def _sharps_for_key(tonic: int, mode: str) -> int:
    """Circle-of-fifths signature for a major key or its relative major."""
    major_tonic = tonic if mode == 'major' else (tonic + 3) % 12
    sharp_tonics = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6, 1: 7}
    flat_tonics = {0: 0, 5: -1, 10: -2, 3: -3, 8: -4, 1: -5, 6: -6}
    if major_tonic in sharp_tonics and major_tonic in flat_tonics:
        # C / ambiguous enharmonics: prefer the smaller alteration.
        sharp, flat = sharp_tonics[major_tonic], flat_tonics[major_tonic]
        return sharp if abs(sharp) <= abs(flat) else flat
    if major_tonic in sharp_tonics:
        return sharp_tonics[major_tonic]
    return flat_tonics.get(major_tonic, 0)


def _reconcile_key_signature(img: ScoreImage, geo: PageGeometry) -> None:
    """
    Drop a scanned key signature that fights the notes on the page.

    A misread signature (3 sharps on a 1-flat plate) rewrites every pitch and
    makes later harmony unrecoverable. Spell once with no signature, read the
    key from those natural pitches, then re-spell with the implied signature.
    """
    if not geo.noteheads or not geo.systems:
        return
    from app.services import harmony as H

    written = geo.systems[0].staves[0].key_sharps if geo.systems[0].staves else 0
    saved = []
    for system in geo.systems:
        for staff in system.staves:
            saved.append((staff, staff.key_sharps))
            staff.key_sharps = 0
    apply_pitches(img, geo)

    free = H.detect_key(H.profile_from_notes(geo.noteheads), None)
    implied = _sharps_for_key(free.tonic, free.mode)
    if abs(implied - written) < 2:
        for staff, value in saved:
            staff.key_sharps = value
        apply_pitches(img, geo)
        return

    for staff, _ in saved:
        staff.key_sharps = implied
    apply_pitches(img, geo)


def analyze_page_geometry(gray: np.ndarray) -> tuple:
    gray, skew = deskew(gray)
    img = ScoreImage(gray)

    staves = detect_staves(img)
    img.strip_staff_lines(staves)
    systems = group_systems(staves, photo=getattr(img, 'photo', False))
    read_staff_headers(img, systems)
    noteheads = detect_noteheads(img, systems)
    measures = build_measures(img, systems, noteheads)
    assign_notes_to_measures(noteheads, measures)

    geo = PageGeometry(
        width=img.width, height=img.height,
        systems=systems, measures=measures, noteheads=noteheads,
        space=float(np.median([s.space for s in staves])) if staves else 17.0,
        skew_deg=skew,
    )
    apply_pitches(img, geo)
    _reconcile_key_signature(img, geo)
    return geo, gray


def debug_render(gray: np.ndarray, geo: PageGeometry, path: str, scale: float = 0.35,
                 labels: bool = False):
    vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for system in geo.systems:
        for staff in system.staves:
            for y in staff.line_ys:
                cv2.line(vis, (int(staff.x_left), int(y)), (int(staff.x_right), int(y)),
                         (255, 200, 0), 1)
            cv2.line(vis, (int(staff.header_end), int(staff.top - 20)),
                     (int(staff.header_end), int(staff.bottom + 20)), (255, 0, 255), 2)
    for m in geo.measures:
        cv2.rectangle(vis, (int(m.x1), int(m.top)), (int(m.x2), int(m.bottom)), (0, 0, 255), 3)
        cv2.putText(vis, str(m.index + 1), (int(m.x1) + 6, int(m.top) + 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
    for n in geo.noteheads:
        color = (0, 170, 0) if n.filled else (200, 0, 200)
        cv2.rectangle(vis, (int(n.x1), int(n.y1)), (int(n.x2), int(n.y2)), color, 2)
        if labels and n.name:
            cv2.putText(vis, n.name, (int(n.x1) - 4, int(n.y1) - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (140, 0, 0), 1)
    cv2.imwrite(path, cv2.resize(vis, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA))
    return path
