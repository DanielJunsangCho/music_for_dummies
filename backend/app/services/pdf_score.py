"""
Read notation straight out of an engraved PDF.

Scores exported by notation software (Finale, Sibelius, MuseScore, Guitar Pro,
LilyPond) draw their symbols with a music font and their staff lines, barlines
and beams as vector paths. When that is the case there is nothing to
*recognise*: the identity and position of every symbol is already in the file.
SMuFL fixes the codepoints, so a notehead is a notehead and its vertical anchor
lands on the staff to within a thousandth of a step.

This module takes that path. Scanned pages carry none of it and fall back to
the computer-vision engine in `score_vision`.

Everything is converted to pixel coordinates of the rendered page image on the
way out, so overlays line up with what the user sees.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from app.services.score_vision import (
    CLEF_TOP_LINE,
    FLAT_ORDER,
    KEY_SIG_POSITIONS,
    LETTER_SEMITONES,
    LETTERS,
    SHARP_ORDER,
    Measure,
    Notehead,
    PageGeometry,
    Staff,
    System,
)

GLYPH_TABLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'data', 'smufl_glyphs.json')

# Music fonts put their glyphs in the Unicode private use area.
PUA_START, PUA_END = 0xE000, 0xF8FF

CLEF_KIND = {
    'gClef': 'treble',
    'fClef': 'bass',
    'cClef': 'alto',
}

ACCIDENTAL_KIND = {
    'accidentalSharp': 'sharp',
    'accidentalFlat': 'flat',
    'accidentalNatural': 'natural',
    'accidentalDoubleSharp': 'double-sharp',
    'accidentalDoubleFlat': 'double-flat',
}

ACCIDENTAL_ALTER = {
    'sharp': 1, 'flat': -1, 'natural': 0, 'double-sharp': 2, 'double-flat': -2,
}

# Note glyphs that bundle a stem with the head. The head sits at one end of
# the glyph rather than at its centre.
STEMMED_NOTE_UP = ('noteWhole', 'noteHalfUp', 'noteQuarterUp', 'note8thUp', 'note16thUp')
STEMMED_NOTE_DOWN = ('noteHalfDown', 'noteQuarterDown', 'note8thDown', 'note16thDown')


@lru_cache(maxsize=1)
def glyph_names() -> dict:
    with open(GLYPH_TABLE) as handle:
        return {int(k, 16): v for k, v in json.load(handle).items()}


@dataclass
class Glyph:
    name: str
    x: float          # anchor: left edge of the symbol
    y: float          # anchor: vertical centre of the symbol
    x0: float
    y0: float
    x1: float
    y1: float
    size: float       # font size in pixels

    @property
    def width(self) -> float:
        return self.x1 - self.x0


@dataclass
class Line:
    y: float
    x0: float
    x1: float


@dataclass
class Bar:
    x: float
    y0: float
    y1: float
    width: float


@dataclass
class PageInk:
    glyphs: list = field(default_factory=list)
    lines: list = field(default_factory=list)
    bars: list = field(default_factory=list)
    width: int = 0
    height: int = 0


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def is_engraved(page) -> bool:
    """True when the page carries music-font glyphs we can read directly."""
    table = glyph_names()
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                for char in span.get('chars', []):
                    cp = ord(char['c'])
                    if PUA_START <= cp <= PUA_END and table.get(cp, '').startswith(
                            ('notehead', 'noteQuarter', 'noteHalf', 'note8th')):
                        return True
    return False


def extract_ink(page, scale: float) -> PageInk:
    """Pull glyphs, horizontal rules and vertical bars in rendered-pixel space."""
    table = glyph_names()
    ink = PageInk(width=int(round(page.rect.width * scale)),
                  height=int(round(page.rect.height * scale)))

    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                size = float(span.get('size', 0.0)) * scale
                for char in span.get('chars', []):
                    cp = ord(char['c'])
                    if not (PUA_START <= cp <= PUA_END):
                        continue
                    name = table.get(cp)
                    if not name:
                        continue
                    x0, y0, x1, y1 = (v * scale for v in char['bbox'])
                    ox, oy = (v * scale for v in char['origin'])
                    ink.glyphs.append(Glyph(name=name, x=ox, y=oy,
                                            x0=x0, y0=y0, x1=x1, y1=y1, size=size))

    for path in page.get_drawings():
        filled = path.get('fill') is not None
        stroke_w = float(path.get('width') or 0.0) * scale
        for item in path['items']:
            kind = item[0]
            if kind == 'l':
                p, q = item[1], item[2]
                px0, py0, px1, py1 = p.x * scale, p.y * scale, q.x * scale, q.y * scale
                if abs(py0 - py1) <= 0.4 and abs(px1 - px0) > 4:
                    ink.lines.append(Line(y=(py0 + py1) / 2,
                                          x0=min(px0, px1), x1=max(px0, px1)))
                elif abs(px0 - px1) <= 0.4 and abs(py1 - py0) > 4:
                    ink.bars.append(Bar(x=(px0 + px1) / 2, y0=min(py0, py1),
                                        y1=max(py0, py1), width=max(stroke_w, 0.6)))
            elif kind == 're':
                r = item[1]
                rx0, ry0 = r.x0 * scale, r.y0 * scale
                rx1, ry1 = r.x1 * scale, r.y1 * scale
                w, h = rx1 - rx0, ry1 - ry0
                if not filled and stroke_w <= 0:
                    continue
                if h > w * 2.5 and h > 4:
                    ink.bars.append(Bar(x=(rx0 + rx1) / 2, y0=ry0, y1=ry1,
                                        width=max(w, stroke_w, 0.6)))
                elif w > h * 4 and w > 4:
                    ink.lines.append(Line(y=(ry0 + ry1) / 2, x0=rx0, x1=rx1))

    return ink


# --------------------------------------------------------------------------
# Staves
# --------------------------------------------------------------------------

def _staff_rules(lines: list, page_width: float, tol: float = 1.2) -> list:
    """
    Collapse horizontal vector segments into candidate staff lines.

    A staff line arrives in pieces - one between each pair of barlines, and
    more if the engraver erased it behind a glyph - so the pieces at one
    height are gathered into a row. Ledger lines sit at exactly those same
    heights, so a row only counts as a staff line if its pieces actually
    cover the width they span. Scattered ledger lines cover almost none of it.
    """
    rows = []
    for line in sorted(lines, key=lambda l: l.y):
        if rows and abs(line.y - rows[-1][0][0]) <= tol:
            rows[-1].append((line.y, line.x0, line.x1))
        else:
            rows.append([(line.y, line.x0, line.x1)])

    rules = []
    for row in rows:
        row.sort(key=lambda p: p[1])
        covered, cursor = 0.0, None
        for _, x0, x1 in row:
            if cursor is None or x0 > cursor:
                covered += x1 - max(x0, cursor if cursor is not None else x0)
                cursor = x1
            elif x1 > cursor:
                covered += x1 - cursor
                cursor = x1
        x_left = min(p[1] for p in row)
        x_right = max(p[2] for p in row)
        extent = x_right - x_left
        if extent < page_width * 0.30 or covered < extent * 0.75:
            continue
        rules.append(Line(y=sum(p[0] for p in row) / len(row), x0=x_left, x1=x_right))

    rules.sort(key=lambda l: l.y)
    return rules


def _extents_match(a: Line, b: Line) -> bool:
    overlap = min(a.x1, b.x1) - max(a.x0, b.x0)
    union = max(a.x1, b.x1) - min(a.x0, b.x0)
    return union > 0 and overlap / union > 0.75


def _staff_groups(rules: list) -> list:
    """
    Find sets of evenly spaced rules that share a horizontal extent.

    Five is a staff and six is tablature; the group is extended past five so
    the two can be told apart rather than a tab staff being read as a staff
    with a stray line under it.
    """
    groups = []
    i = 0
    while i + 4 < len(rules):
        window = rules[i:i + 5]
        gaps = [b.y - a.y for a, b in zip(window, window[1:])]
        base = sum(gaps) / len(gaps)
        if base <= 0 or max(abs(g - base) for g in gaps) > base * 0.15 \
                or not all(_extents_match(window[0], r) for r in window[1:]):
            i += 1
            continue
        take = 5
        while i + take < len(rules):
            nxt = rules[i + take]
            if abs(nxt.y - rules[i + take - 1].y - base) > base * 0.15 \
                    or not _extents_match(window[0], nxt):
                break
            take += 1
            if take >= 8:
                break
        groups.append(rules[i:i + take])
        i += take
    return groups


def detect_staves(ink: PageInk) -> list:
    """Group vector rules into staves. Six-line tab groups are kept for now."""
    if not ink.lines:
        return []
    rules = _staff_rules(ink.lines, ink.width)

    staves = []
    for group in _staff_groups(rules):
        while len(group) >= 5:
            take = 6 if len(group) == 6 else 5
            chunk = group[:take]
            staves.append(Staff(
                line_ys=[l.y for l in chunk],
                x_left=min(l.x0 for l in chunk),
                x_right=max(l.x1 for l in chunk),
            ))
            group = group[take:]
    return staves


def attach_clefs(ink: PageInk, staves: list) -> list:
    """
    Label each staff from its clef glyph and drop the ones we cannot read.

    Tablature is explicit here: `6stringTabClef` says so outright, which is
    far safer than guessing from the number of lines.
    """
    kept = []
    for staff in staves:
        space = staff.space
        best = None
        for g in ink.glyphs:
            if not g.name.endswith('Clef') and 'Clef' not in g.name:
                continue
            if not (staff.top - space * 2 <= g.y <= staff.bottom + space * 2):
                continue
            if g.x > staff.x_left + space * 12:
                continue
            if best is None or g.x < best.x:
                best = g
        if best is None:
            # No clef found: keep 5-line staves as treble, drop odd ones.
            if len(staff.line_ys) == 5:
                kept.append(staff)
            continue
        if 'Tab' in best.name or len(staff.line_ys) != 5:
            continue
        staff.clef = CLEF_KIND.get(best.name, 'treble')
        staff.header_end = best.x1
        kept.append(staff)
    return kept


def group_systems(staves: list, ink: PageInk) -> list:
    """
    A system is the set of staves played at once.

    Staves are joined when a single barline runs through both of them, and
    otherwise when they sit far closer together than the usual staff spacing.
    """
    staves = sorted(staves, key=lambda s: s.top)
    if not staves:
        return []

    gaps = [b.top - a.bottom for a, b in zip(staves, staves[1:])]
    typical = sorted(gaps)[len(gaps) // 2] if gaps else 0.0

    systems, current = [], [staves[0]]
    for prev, staff in zip(staves, staves[1:]):
        spanned = any(bar.y0 <= prev.top + 2 and bar.y1 >= staff.bottom - 2
                      and bar.y1 - bar.y0 > (staff.bottom - prev.top) * 0.9
                      for bar in ink.bars)
        close = typical > 0 and (staff.top - prev.bottom) < typical * 0.55
        if spanned or close:
            current.append(staff)
        else:
            systems.append(System(staves=current, index=len(systems)))
            current = [staff]
    systems.append(System(staves=current, index=len(systems)))
    return systems


# --------------------------------------------------------------------------
# Header: key signature and time signature
# --------------------------------------------------------------------------

def _position_of(staff: Staff, y: float) -> int:
    return int(round((y - staff.top) / (staff.space / 2.0)))


def read_key_signature(ink: PageInk, staff: Staff) -> None:
    """
    Count the accidentals in the run right after the clef.

    They must sit at the canonical staff positions and follow the standard
    order, which rules out an early accidental that belongs to a note.
    """
    space = staff.space
    clef_end = staff.header_end or staff.x_left
    candidates = sorted(
        (g for g in ink.glyphs
         if g.name in ('accidentalSharp', 'accidentalFlat')
         and staff.top - space * 2.5 <= g.y <= staff.bottom + space * 2.5
         and clef_end - space * 0.5 <= g.x <= clef_end + space * 22),
        key=lambda g: g.x)

    for kind, glyph_name in (('sharp', 'accidentalSharp'), ('flat', 'accidentalFlat')):
        run = []
        cursor = clef_end
        for g in candidates:
            if g.name != glyph_name:
                continue
            if g.x - cursor > space * 3.0:
                break
            run.append(g)
            cursor = g.x1
        if not run:
            continue
        wanted = KEY_SIG_POSITIONS.get((staff.clef, kind))
        if not wanted:
            continue
        count = 0
        for i, g in enumerate(run):
            if i >= len(wanted):
                break
            if abs(_position_of(staff, g.y) - wanted[i]) > 0:
                break
            count += 1
        if count:
            staff.key_sharps = count if kind == 'sharp' else -count
            staff.header_end = max(staff.header_end, run[count - 1].x1)
            return


def read_time_signatures(ink: PageInk, staff: Staff) -> list:
    """
    Every time signature on a staff, with the x it takes effect at.

    A piece can change meter, and often does so immediately: a waltz with a
    two-beat pickup is written as one 2/4 bar followed by 3/4. Reading only
    the first one would misread the whole piece.
    """
    space = staff.space
    found = []

    for g in ink.glyphs:
        if g.name not in ('timeSigCommon', 'timeSigCutCommon'):
            continue
        if staff.top - space <= g.y <= staff.bottom + space:
            found.append((g.x, (2, 2) if 'Cut' in g.name else (4, 4), g.x1))

    digits = sorted((g for g in ink.glyphs
                     if g.name.startswith('timeSig') and g.name[len('timeSig'):].isdigit()
                     and staff.top - space <= g.y <= staff.bottom + space),
                    key=lambda g: g.x)

    # Digits of one time signature are stacked at the same x; a later change
    # sits further along the staff.
    clusters = []
    for g in digits:
        if clusters and g.x - clusters[-1][-1].x <= space * 1.2:
            clusters[-1].append(g)
        else:
            clusters.append([g])

    for cluster in clusters:
        upper = [g for g in cluster if g.y < staff.y_center]
        lower = [g for g in cluster if g.y >= staff.y_center]

        def value(group: list) -> Optional[int]:
            text = ''.join(g.name[len('timeSig'):] for g in sorted(group, key=lambda g: g.x))
            return int(text) if text else None

        num, den = value(upper), value(lower)
        if num and den:
            found.append((min(g.x for g in cluster), (num, den),
                          max(g.x1 for g in cluster)))

    found.sort()
    if found and found[0][0] <= staff.header_end + space * 6:
        staff.header_end = max(staff.header_end, found[0][2])
    return [(x, meter) for x, meter, _ in found]


# --------------------------------------------------------------------------
# Notes
# --------------------------------------------------------------------------

def _head_anchor(glyph: Glyph, space: float) -> Optional[tuple]:
    """Where the notehead sits inside a glyph, and whether it is filled."""
    name = glyph.name
    if name.startswith('notehead'):
        if 'Black' in name:
            filled = True
        elif 'Half' in name or 'Whole' in name or 'White' in name:
            filled = False
        elif name == 'noteheadNull' or 'Parenthesis' in name:
            return None
        else:
            filled = True
        return glyph.x + space * 0.58, glyph.y, filled
    if name.startswith(STEMMED_NOTE_UP):
        return glyph.x + space * 0.58, glyph.y1 - space * 0.5, 'Quarter' in name or '8th' in name or '16th' in name
    if name.startswith(STEMMED_NOTE_DOWN):
        return glyph.x + space * 0.58, glyph.y0 + space * 0.5, 'Quarter' in name or '8th' in name or '16th' in name
    return None


def collect_noteheads(ink: PageInk, systems: list) -> list:
    """Turn notehead glyphs into notes bound to the staff they sit on."""
    notes = []
    for system in systems:
        for staff in system.staves:
            space = staff.space
            # Vertical reach of a staff: about two octaves of ledger lines.
            lo, hi = staff.top - space * 7.5, staff.bottom + space * 7.5
            for g in ink.glyphs:
                if not (lo <= g.y <= hi):
                    continue
                if not (staff.x_left - space <= g.x <= staff.x_right + space):
                    continue
                anchor = _head_anchor(g, space)
                if anchor is None:
                    continue
                cx, cy, filled = anchor
                if not (lo <= cy <= hi):
                    continue
                half_w, half_h = space * 0.62, space * 0.52
                notes.append(Notehead(
                    cx=cx, cy=cy,
                    x1=cx - half_w, y1=cy - half_h,
                    x2=cx + half_w, y2=cy + half_h,
                    filled=bool(filled), staff=staff, system_index=system.index,
                    staff_position=_position_of(staff, cy),
                ))
    return _dedupe(notes)


def _dedupe(notes: list) -> list:
    """Drop glyphs stacked on the same spot (an engraver drawing a head twice)."""
    kept = []
    for note in sorted(notes, key=lambda n: (n.cx, n.cy)):
        space = note.staff.space
        if any(abs(note.cx - k.cx) < space * 0.4 and abs(note.cy - k.cy) < space * 0.3
               and k.staff is note.staff for k in kept):
            continue
        kept.append(note)
    return kept


# --------------------------------------------------------------------------
# Measures
# --------------------------------------------------------------------------

def build_measures(ink: PageInk, systems: list, index_from: int = 0) -> list:
    measures = []
    index = index_from
    for system in systems:
        space = system.staves[0].space
        top, bottom = system.top, system.bottom

        # A barline runs from the top staff line to the bottom one and stops
        # there. A stem is about as tall but starts at a notehead and ends at
        # a beam, so matching both endpoints separates the two cleanly.
        tol = space * 0.35
        spans = [(top, bottom)] + [(s.top, s.bottom) for s in system.staves]
        xs = []
        for bar in ink.bars:
            if bar.width > space * 0.9:
                continue
            if not (system.x_left - space <= bar.x <= system.x_right + space):
                continue
            if any(abs(bar.y0 - a) <= tol and abs(bar.y1 - b) <= tol for a, b in spans):
                xs.append(bar.x)

        edges = [system.staves[0].header_end or system.x_left]
        for x in sorted(xs):
            if x <= edges[0] + space:
                continue
            if edges and abs(x - edges[-1]) < space * 1.5:
                continue
            edges.append(x)
        if edges[-1] < system.x_right - space:
            edges.append(system.x_right)

        for x1, x2 in zip(edges, edges[1:]):
            measures.append(Measure(
                system_index=system.index, index=index,
                x1=float(x1), x2=float(x2),
                top=float(top - space * 1.5), bottom=float(bottom + space * 1.5),
            ))
            index += 1
    return measures


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


def _bind_accidentals(ink: PageInk, noteheads: list) -> dict:
    """
    Match each accidental to the one notehead it belongs to.

    An accidental sits immediately left of its note at the same height, but
    in a chord the accidentals are fanned out to the left to avoid colliding,
    so the nearest unclaimed note at that height wins rather than the nearest
    note outright.
    """
    bound = {}
    claimed = set()
    accidentals = sorted((g for g in ink.glyphs if g.name in ACCIDENTAL_KIND),
                         key=lambda g: -g.x)

    for g in accidentals:
        best, best_gap = None, None
        for note in noteheads:
            space = note.staff.space
            if abs(g.y - note.cy) > space * 0.35:
                continue
            gap = note.x1 - g.x1
            if not (-space * 0.2 <= gap <= space * 4.5):
                continue
            if id(note) in claimed:
                continue
            if best_gap is None or gap < best_gap:
                best, best_gap = note, gap
        if best is not None:
            claimed.add(id(best))
            bound[id(best)] = ACCIDENTAL_KIND[g.name]
    return bound


def apply_pitches(ink: PageInk, geo: PageGeometry) -> None:
    """
    Resolve every note to a pitch.

    An accidental binds to the notehead immediately to its right at the same
    height, and then stays in force for that measure, which is what the
    notation actually means.
    """
    bound = _bind_accidentals(ink, geo.noteheads)

    for measure in geo.measures:
        active = {}
        for note in sorted(measure.noteheads, key=lambda n: (n.cx, n.cy)):
            staff = note.staff
            kind = bound.get(id(note))

            letter, octave = _pitch_from_position(note.staff_position, staff.clef)
            if kind is not None:
                alter = ACCIDENTAL_ALTER[kind]
                active[(letter, octave)] = alter
            else:
                alter = active.get((letter, octave),
                                   _key_alteration(letter, staff.key_sharps))

            note.accidental = kind
            note.midi = (octave + 1) * 12 + LETTER_SEMITONES[letter] + alter
            suffix = {1: '#', 2: '##', -1: 'b', -2: 'bb'}.get(alter, '')
            note.name = f'{letter}{suffix}{octave}'


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------

def analyze_page(page, scale: float) -> Optional[PageGeometry]:
    """Read one engraved page, or None if it turns out not to be readable."""
    ink = extract_ink(page, scale)
    staves = attach_clefs(ink, detect_staves(ink))
    if not staves:
        return None

    systems = group_systems(staves, ink)
    meter_marks = []
    for system in systems:
        for staff in system.staves:
            read_key_signature(ink, staff)
            for x, meter in read_time_signatures(ink, staff):
                meter_marks.append((system.index, x, meter))

    # A key signature is written on every system; trust the majority.
    votes = {}
    for system in systems:
        for staff in system.staves:
            votes[staff.key_sharps] = votes.get(staff.key_sharps, 0) + 1
    if votes:
        winner = max(votes.items(), key=lambda kv: (kv[1], -abs(kv[0])))[0]
        for system in systems:
            for staff in system.staves:
                staff.key_sharps = winner

    noteheads = collect_noteheads(ink, systems)
    measures = build_measures(ink, systems)

    by_system = {}
    for m in measures:
        by_system.setdefault(m.system_index, []).append(m)
    for note in noteheads:
        for measure in by_system.get(note.system_index, []):
            if measure.x1 <= note.cx <= measure.x2:
                note.measure_index = measure.index
                measure.noteheads.append(note)
                break

    spaces = sorted(s.space for sys in systems for s in sys.staves)
    geo = PageGeometry(
        width=ink.width, height=ink.height,
        systems=systems, measures=measures, noteheads=noteheads,
        space=spaces[len(spaces) // 2] if spaces else 17.0,
        skew_deg=0.0,
    )
    apply_pitches(ink, geo)

    # Tie each meter change to the measure it starts in.
    changes = {}
    for system_index, x, meter in sorted(meter_marks, key=lambda m: (m[0], m[1])):
        target = next((m for m in measures if m.system_index == system_index
                       and m.x1 - geo.space <= x <= m.x2), None)
        if target is None:
            target = next((m for m in measures if m.system_index == system_index), None)
        if target is not None:
            changes.setdefault(target.index, meter)
    geo.meter_changes = sorted(changes.items())
    geo.time_signature = geo.meter_changes[0][1] if geo.meter_changes else None
    return geo
