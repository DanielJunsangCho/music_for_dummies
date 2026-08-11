"""
Validate the harmony engine against symbolic ground truth.

This deliberately bypasses scan/PDF vision: pitches come from MusicXML or
TheoryTab, so failures are about chord labelling, key finding, and harmonic
rhythm — not notehead detection.

Supported fixtures
------------------
* When-in-Rome: ``score.mxl`` + ``analysis.txt`` (RomanText)
* Hooktheory TheoryTab: melody is ignored; chord symbols are realised as
  block-chord noteheads so we can ask whether the engine recovers the
  annotated roots.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from music21 import chord as m21chord
from music21 import converter
from music21 import key as m21key
from music21 import meter
from music21 import note as m21note
from app.services import harmony as H
from app.services.score_vision import Measure, Notehead, PageGeometry, Staff, System

FIXTURES = Path(__file__).parent / 'fixtures' / 'symbolic'

# TheoryTab mode index → major-scale degree offsets from tonic.
# mode 1 = major / Ionian; Hooktheory stores sd relative to that mode.
_MODE_OFFSETS = {
    1: [0, 2, 4, 5, 7, 9, 11],   # major
    2: [0, 2, 3, 5, 7, 9, 10],   # dorian
    3: [0, 1, 3, 5, 7, 8, 10],   # phrygian
    4: [0, 2, 4, 6, 7, 9, 11],   # lydian
    5: [0, 2, 4, 5, 7, 9, 10],   # mixolydian
    6: [0, 2, 3, 5, 7, 8, 10],   # aeolian / natural minor
    7: [0, 1, 3, 5, 6, 8, 10],   # locrian
}

_PC_NAME = {
    'C': 0, 'B#': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
    'E': 4, 'Fb': 4, 'E#': 5, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7,
    'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11, 'Cb': 11,
}


@dataclass
class GroundTruthChord:
    measure: int          # 1-based measure number from the source
    beat: float           # 1-based beat
    root: int             # pitch class 0-11
    figure: str
    key_name: Optional[str] = None


@dataclass
class EvalResult:
    name: str
    predicted_key: str
    measures: int
    notes: int
    chords: int
    root_recall: float
    root_precision: float
    key_accuracy: float
    change_recall: float
    details: list


def _norm_key_name(name: str) -> str:
    return name.replace('-', 'b').replace(' ', '').lower()


def _geometry_from_events(
    by_measure: dict,
    *,
    time_signature: Optional[tuple],
    key_sharps: int,
) -> tuple[PageGeometry, list[int]]:
    staff = Staff(
        line_ys=[100, 110, 120, 130, 140],
        x_left=40,
        x_right=800,
        clef='treble',
        key_sharps=key_sharps,
        header_end=60,
    )
    system = System(staves=[staff], index=0)
    measures = []
    noteheads = []
    ordered = sorted(by_measure)
    beats = float(time_signature[0]) if time_signature else 4.0

    for index, measure_number in enumerate(ordered):
        x1 = 80.0 + index * 120.0
        x2 = x1 + 110.0
        measure = Measure(
            system_index=0,
            index=index,
            x1=x1,
            x2=x2,
            top=80.0,
            bottom=160.0,
            noteheads=[],
        )
        for beat, midi in by_measure[measure_number]:
            frac = (beat - 1.0) / max(1.0, beats)
            frac = min(max(frac, 0.0), 0.95)
            cx = x1 + 10.0 + frac * (x2 - x1 - 20.0)
            cy = 120.0
            head = Notehead(
                cx=cx,
                cy=cy,
                x1=cx - 4,
                y1=cy - 4,
                x2=cx + 4,
                y2=cy + 4,
                filled=True,
                staff=staff,
                system_index=0,
                midi=int(midi),
                name=H.pitch_name(int(midi) % 12, True),
                measure_index=index,
            )
            measure.noteheads.append(head)
            noteheads.append(head)
        measures.append(measure)

    geometry = PageGeometry(
        width=1000,
        height=400,
        systems=[system],
        measures=measures,
        noteheads=noteheads,
        space=10.0,
        time_signature=time_signature,
        source='engraved',
    )
    return geometry, ordered


def geometry_from_musicxml(path: Path) -> tuple[PageGeometry, list[int]]:
    score = converter.parse(str(path))
    try:
        score = score.expandRepeats()
    except Exception:
        pass

    time_signature = None
    stamps = list(score.recurse().getElementsByClass(meter.TimeSignature))
    if stamps:
        time_signature = (stamps[0].numerator, stamps[0].denominator)

    key_sharps = 0
    signatures = list(score.recurse().getElementsByClass(m21key.KeySignature))
    if signatures:
        key_sharps = signatures[0].sharps

    by_measure: dict[int, list[tuple[float, int]]] = {}
    parts = list(score.parts) if score.parts else [score]
    for part in parts:
        for measure in part.getElementsByClass('Measure'):
            number = measure.measureNumber
            if number is None:
                continue
            bucket = by_measure.setdefault(number, [])
            for element in measure.recurse().notes:
                if isinstance(element, m21note.Note):
                    midis = [element.pitch.midi]
                elif isinstance(element, m21chord.Chord):
                    midis = [pitch.midi for pitch in element.pitches]
                else:
                    continue
                beat = float(element.beat) if element.beat is not None else 1.0
                for midi in midis:
                    bucket.append((beat, midi))

    return _geometry_from_events(
        by_measure,
        time_signature=time_signature,
        key_sharps=key_sharps,
    )


def ground_truth_from_romantext(path: Path) -> list[GroundTruthChord]:
    analysis = converter.parse(str(path), format='romantext')
    items = []
    for numeral in analysis.recurse().getElementsByClass('RomanNumeral'):
        number = numeral.measureNumber
        if number is None:
            continue
        key_name = None
        if numeral.key is not None:
            key_name = f'{numeral.key.tonic.name} {numeral.key.mode}'
        items.append(GroundTruthChord(
            measure=int(number),
            beat=float(numeral.beat) if numeral.beat is not None else 1.0,
            root=int(numeral.root().pitchClass),
            figure=numeral.figure,
            key_name=key_name,
        ))
    return items


def _theorytab_root(sd: int, tonic: int, mode: int, borrowed: Optional[str]) -> int:
    offsets = list(_MODE_OFFSETS.get(mode, _MODE_OFFSETS[1]))
    # borrowed: negative = parallel minor degrees, etc. Keep simple: if borrowed
    # is set and mode is major, use natural-minor offsets for that chord.
    if borrowed not in (None, '', '0') and mode == 1:
        offsets = _MODE_OFFSETS[6]
    return (tonic + offsets[(sd - 1) % 7]) % 12


def _theorytab_quality_pcs(root: int, sd: int, mode: int,
                           fb: Optional[str], sus: Optional[str]) -> list[int]:
    """Return sounding pitch classes for a simple TheoryTab chord."""
    if sus == 'sus2':
        intervals = [0, 2, 7]
    elif sus == 'sus4':
        intervals = [0, 5, 7]
    elif fb in ('m', 'min'):
        intervals = [0, 3, 7]
    elif fb in ('m7', 'min7'):
        intervals = [0, 3, 7, 10]
    elif fb in ('maj7', 'M7'):
        intervals = [0, 4, 7, 11]
    elif fb == '6':
        intervals = [0, 4, 7, 9]
    elif fb == '7':
        intervals = [0, 4, 7, 10]
    elif fb == '9':
        intervals = [0, 4, 7, 10, 2]
    elif fb in (None, '', '5'):
        # Empty figured bass = diatonic triad in the active mode.
        if mode == 1 and sd in (2, 3, 6):
            intervals = [0, 3, 7]
        elif mode == 1 and sd == 7:
            intervals = [0, 3, 6]
        elif mode == 6 and sd in (1, 4, 5):
            intervals = [0, 3, 7]
        else:
            intervals = [0, 4, 7]
    else:
        intervals = [0, 4, 7]
    return [(root + interval) % 12 for interval in intervals]


def geometry_and_truth_from_theorytab(path: Path) -> tuple[PageGeometry, list[int], list[GroundTruthChord]]:
    root = ET.parse(path).getroot()
    key_name = root.findtext('.//key') or 'C'
    mode = int(root.findtext('.//mode') or '1')
    beats = int(root.findtext('.//beats_in_measure') or '4')
    tonic = _PC_NAME[key_name.replace('b', 'b').replace('#', '#')]
    # Hooktheory key is a letter; flats come as b in some files.
    if key_name not in _PC_NAME:
        tonic = _PC_NAME.get(key_name[:1], 0)

    key_label = f"{key_name} {'major' if mode == 1 else 'minor'}"
    by_measure: dict[int, list[tuple[float, int]]] = {}
    truth: list[GroundTruthChord] = []

    for node in root.findall('.//chord'):
        if (node.findtext('isRest') or '0') == '1':
            continue
        sd = int(node.findtext('sd') or '1')
        measure = int(node.findtext('start_measure') or '1')
        beat = float(node.findtext('start_beat') or '1')
        fb = node.findtext('fb')
        sus = node.findtext('sus')
        borrowed = node.findtext('borrowed')
        chord_root = _theorytab_root(sd, tonic, mode, borrowed)
        # Build a readable figure for reporting.
        figure = f'sd{sd}'
        if fb:
            figure += fb
        if sus:
            figure += sus

        truth.append(GroundTruthChord(
            measure=measure,
            beat=beat,
            root=chord_root,
            figure=figure,
            key_name=key_label,
        ))
        # Realise as a mid-register block chord with the root lowest.
        for pc in _theorytab_quality_pcs(chord_root, sd, mode, fb, sus):
            midi = (48 + pc) if pc == chord_root else (60 + pc)
            by_measure.setdefault(measure, []).append((beat, midi))

    # Sharps for key signature hint only; pitch classes are absolute.
    major_sharps = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6, 1: -5, 8: -4, 3: -3, 10: -2, 5: -1}
    geometry, ordered = _geometry_from_events(
        by_measure,
        time_signature=(beats, 4),
        key_sharps=major_sharps.get(tonic, 0) if mode == 1 else major_sharps.get((tonic + 3) % 12, 0),
    )
    return geometry, ordered, truth


def evaluate(geometry: PageGeometry, measure_numbers: list[int], truth: list[GroundTruthChord],
             name: str) -> EvalResult:
    reading = H.analyze([{'geometry': geometry, 'page': 1}])
    spans = [span for _, span in reading['spans']]
    keys = reading.get('keys') or [reading['key']]

    truth_by_measure: dict[int, list[GroundTruthChord]] = {}
    for item in truth:
        truth_by_measure.setdefault(item.measure, []).append(item)

    recalled = total_gt = 0
    precise = total_pred = 0
    key_hits = key_total = 0
    change_hits = change_total = 0
    details = []

    for index, measure_number in enumerate(measure_numbers):
        predicted = [span for span in spans if span.measure_index == index]
        expected = truth_by_measure.get(measure_number, [])
        if not expected:
            continue

        pred_roots = [span.root % 12 for span in predicted]
        gt_roots = [item.root % 12 for item in expected]
        pred_set = set(pred_roots)
        gt_set = set(gt_roots)

        for root in gt_roots:
            total_gt += 1
            if root in pred_set:
                recalled += 1
        for root in pred_roots:
            total_pred += 1
            if root in gt_set:
                precise += 1

        if len(gt_set) > 1:
            change_total += 1
            if len(pred_set) > 1:
                change_hits += 1

        if expected[0].key_name and predicted:
            key_total += 1
            local = keys[predicted[0].key_index]
            if _norm_key_name(local.name) == _norm_key_name(expected[0].key_name):
                key_hits += 1

        details.append({
            'measure': measure_number,
            'gt': [item.figure for item in expected],
            'gt_roots': sorted(gt_set),
            'pred': [f'{span.symbol}/{span.roman}' for span in predicted],
            'pred_roots': sorted(pred_set),
        })

    return EvalResult(
        name=name,
        predicted_key=reading['key'].name,
        measures=len(geometry.measures),
        notes=len(geometry.noteheads),
        chords=len(spans),
        root_recall=recalled / total_gt if total_gt else 0.0,
        root_precision=precise / total_pred if total_pred else 0.0,
        key_accuracy=key_hits / key_total if key_total else 0.0,
        change_recall=change_hits / change_total if change_total else 1.0,
        details=details,
    )


def evaluate_when_in_rome(piece_dir: Path) -> EvalResult:
    geometry, measure_numbers = geometry_from_musicxml(piece_dir / 'score.mxl')
    truth = ground_truth_from_romantext(piece_dir / 'analysis.txt')
    return evaluate(geometry, measure_numbers, truth, piece_dir.name)


def evaluate_theorytab(path: Path) -> EvalResult:
    geometry, measure_numbers, truth = geometry_and_truth_from_theorytab(path)
    return evaluate(geometry, measure_numbers, truth, path.stem)
