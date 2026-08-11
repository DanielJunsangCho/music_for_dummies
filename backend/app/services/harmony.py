"""
Harmony engine.

Turns the noteheads found by the score-vision pass into a harmonic reading:
chord segments, keys (including modulations), Roman numerals, functions and
cadences.

The engine is built around three ideas:

1. Harmonic rhythm is chosen, not assumed. Each measure is tried at one,
   two and four chords per measure, and the segmentation that explains the
   notes best - after a penalty for changing chords more often - wins.
2. Chords are scored against weighted templates, so a missing fifth costs
   little while a missing third costs a lot, and the bass note pulls the
   answer toward the root it implies.
3. The chord sequence is smoothed with Viterbi over a transition model that
   prefers staying put, moving by fifths, and staying inside the key. This
   is what stops one misread notehead from inventing a chord change.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

PITCH_NAMES_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
PITCH_NAMES_FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

# Interval sets and how much each degree matters when it is missing.
# (name, suffix, {interval: weight}, essential intervals, complexity)
CHORD_TEMPLATES = [
    ('major',            '',      {0: 1.0, 4: 1.0, 7: 0.7},                    (0, 4), 0.0),
    ('minor',            'm',     {0: 1.0, 3: 1.0, 7: 0.7},                    (0, 3), 0.0),
    ('diminished',       'dim',   {0: 1.0, 3: 1.0, 6: 1.0},                    (0, 3, 6), 0.25),
    ('augmented',        'aug',   {0: 1.0, 4: 1.0, 8: 1.0},                    (0, 4, 8), 0.45),
    ('suspended fourth', 'sus4',  {0: 1.0, 5: 1.0, 7: 0.8},                    (0, 5), 0.35),
    ('suspended second', 'sus2',  {0: 1.0, 2: 1.0, 7: 0.8},                    (0, 2), 0.45),
    ('dominant seventh', '7',     {0: 1.0, 4: 0.9, 7: 0.5, 10: 1.0},           (0, 4, 10), 0.15),
    ('major seventh',    'maj7',  {0: 1.0, 4: 0.9, 7: 0.5, 11: 1.0},           (0, 4, 11), 0.2),
    ('minor seventh',    'm7',    {0: 1.0, 3: 0.9, 7: 0.5, 10: 1.0},           (0, 3, 10), 0.2),
    ('half-diminished',  'm7b5',  {0: 1.0, 3: 0.9, 6: 1.0, 10: 0.9},           (0, 3, 6, 10), 0.4),
    ('diminished seventh', 'dim7', {0: 1.0, 3: 0.9, 6: 1.0, 9: 1.0},           (0, 3, 6, 9), 0.4),
    ('minor-major seventh', 'mMaj7', {0: 1.0, 3: 0.9, 7: 0.5, 11: 1.0},        (0, 3, 11), 0.6),
    ('sixth',            '6',     {0: 1.0, 4: 0.9, 7: 0.5, 9: 0.9},            (0, 4, 9), 0.35),
    ('minor sixth',      'm6',    {0: 1.0, 3: 0.9, 7: 0.5, 9: 0.9},            (0, 3, 9), 0.4),
    ('added ninth',      'add9',  {0: 1.0, 2: 0.8, 4: 0.9, 7: 0.5},            (0, 4, 2), 0.4),
    ('dominant ninth',   '9',     {0: 1.0, 2: 0.7, 4: 0.9, 7: 0.4, 10: 0.9},   (0, 4, 10, 2), 0.45),
    ('minor ninth',      'm9',    {0: 1.0, 2: 0.7, 3: 0.9, 7: 0.4, 10: 0.9},   (0, 3, 10, 2), 0.5),
    ('dominant seventh flat ninth', '7b9', {0: 1.0, 1: 0.8, 4: 0.9, 7: 0.4, 10: 0.9}, (0, 4, 10, 1), 0.55),
]

# Krumhansl-Kessler profiles, used to pick a key from note content.
MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10, 11]

ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII']
DEGREE_OF_SEMITONE_MAJOR = {0: (1, ''), 1: (2, 'b'), 2: (2, ''), 3: (3, 'b'), 4: (3, ''),
                            5: (4, ''), 6: (5, 'b'), 7: (5, ''), 8: (6, 'b'), 9: (6, ''),
                            10: (7, 'b'), 11: (7, '')}
DEGREE_OF_SEMITONE_MINOR = {0: (1, ''), 1: (2, 'b'), 2: (2, ''), 3: (3, ''), 4: (3, '#'),
                            5: (4, ''), 6: (5, 'b'), 7: (5, ''), 8: (6, ''), 9: (6, '#'),
                            10: (7, ''), 11: (7, '#')}


@dataclass
class Key:
    tonic: int
    mode: str  # 'major' | 'minor'
    confidence: float = 0.0

    @property
    def name(self) -> str:
        names = PITCH_NAMES_SHARP if self.prefers_sharps else PITCH_NAMES_FLAT
        return f"{names[self.tonic % 12]} {self.mode}"

    @property
    def prefers_sharps(self) -> bool:
        sharp_keys = {7, 2, 9, 4, 11, 6, 1}  # G D A E B F# C#
        return self.tonic % 12 in sharp_keys or self.tonic % 12 == 0

    def scale(self) -> list:
        base = MAJOR_SCALE if self.mode == 'major' else MINOR_SCALE
        return [(self.tonic + i) % 12 for i in base]


@dataclass
class ChordSpan:
    """One chord, anchored to the noteheads that produced it."""
    measure_index: int
    system_index: int
    beat: float
    beats: float
    x1: float
    x2: float
    root: int
    quality: str
    suffix: str
    confidence: float
    pitch_classes: list
    note_ids: list = field(default_factory=list)
    bass: Optional[int] = None
    roman: str = ''
    function: str = ''
    key_index: int = 0
    inversion: int = 0
    tonicizes: Optional[str] = None
    bass_name: Optional[str] = None
    prefers_sharps: bool = True

    @property
    def symbol(self) -> str:
        names = PITCH_NAMES_SHARP if self.prefers_sharps else PITCH_NAMES_FLAT
        base = f"{names[self.root % 12]}{self.suffix}"
        if self.bass is not None and self.bass % 12 != self.root % 12:
            # Prefer the spelling actually printed in the score: an engraver
            # writing G natural means G, not F double sharp.
            base += f"/{self.bass_name or names[self.bass % 12]}"
        return base


def pitch_name(pc: int, sharps: bool = True) -> str:
    names = PITCH_NAMES_SHARP if sharps else PITCH_NAMES_FLAT
    return names[pc % 12]


# --------------------------------------------------------------------------
# Segmentation
# --------------------------------------------------------------------------

def group_onsets(noteheads: list, space: float) -> list:
    """Cluster noteheads that are written at the same horizontal position."""
    if not noteheads:
        return []
    tolerance = space * 1.15
    ordered = sorted(noteheads, key=lambda n: n.cx)
    groups = [[ordered[0]]]
    for note in ordered[1:]:
        if note.cx - groups[-1][-1].cx <= tolerance:
            groups[-1].append(note)
        else:
            groups.append([note])
    return groups


def _note_weight(note) -> float:
    """Longer notes carry more harmonic weight; hollow heads last longer."""
    return 2.0 if not note.filled else 1.0


def profile_from_notes(notes: list) -> list:
    profile = [0.0] * 12
    for note in notes:
        if not note.midi:
            continue
        profile[note.midi % 12] += _note_weight(note)
    return profile


# --------------------------------------------------------------------------
# Chord scoring
# --------------------------------------------------------------------------

def key_prior(root: int, quality: str, key: Optional[Key]) -> float:
    """
    Mild preference for chords that belong to the key.

    Kept small on purpose: this music is full of secondary dominants and
    passing diminished chords, and a heavy prior would flatten them into
    diatonic mush.
    """
    if key is None:
        return 0.0
    scale = set(key.scale())
    degree = (root - key.tonic) % 12
    bonus = 0.0
    if root % 12 in scale:
        bonus += 0.05
    else:
        bonus -= 0.06

    major_diatonic = {0: 'major', 2: 'minor', 4: 'minor', 5: 'major',
                      7: 'major', 9: 'minor', 11: 'diminished'}
    minor_diatonic = {0: 'minor', 2: 'diminished', 3: 'major', 5: 'minor',
                      7: 'major', 8: 'major', 10: 'major'}
    table = major_diatonic if key.mode == 'major' else minor_diatonic
    expected = table.get(degree)
    if expected and quality.startswith(expected):
        bonus += 0.05

    # Secondary dominants resolve down a fifth onto a scale degree.
    if quality in ('dominant seventh', 'major', 'dominant ninth', 'dominant seventh flat ninth'):
        target = (root + 5) % 12
        if target in scale:
            bonus += 0.035
    return bonus


def score_chord(profile: list, bass_pc: Optional[int], key: Optional[Key] = None) -> list:
    """
    Score every root/quality against a pitch-class profile.

    Returns candidates sorted best first as (score, root, name, suffix).
    """
    total = sum(profile)
    if total <= 0:
        return []

    results = []
    for root in range(12):
        for name, suffix, intervals, essential, complexity in CHORD_TEMPLATES:
            covered = 0.0
            template_weight = 0.0
            missing_penalty = 0.0

            for interval, weight in intervals.items():
                pc = (root + interval) % 12
                template_weight += weight
                present = profile[pc]
                if present > 0:
                    covered += weight * min(1.0, present / (total / 3.0) + 0.55)
                elif interval in essential:
                    missing_penalty += weight * 0.85
                else:
                    missing_penalty += weight * 0.18

            chord_pcs = {(root + i) % 12 for i in intervals}
            outside = sum(w for pc, w in enumerate(profile) if pc not in chord_pcs)
            outside_ratio = outside / total

            score = covered / max(template_weight, 1e-6)
            score -= missing_penalty / max(template_weight, 1e-6) * 0.9
            score -= outside_ratio * 1.15
            score -= complexity * 0.16

            if bass_pc is not None:
                if bass_pc == root:
                    score += 0.16
                elif bass_pc in chord_pcs:
                    score += 0.02
                else:
                    score -= 0.14

            score += key_prior(root, name, key)
            results.append((score, root, name, suffix))

    results.sort(key=lambda r: -r[0])
    return results


# --------------------------------------------------------------------------
# Key detection
# --------------------------------------------------------------------------

def detect_key(profile: list, key_sharps: Optional[int] = None) -> Key:
    """
    Correlate a pitch-class profile with the Krumhansl key profiles.

    When the printed key signature is known it constrains the answer to that
    signature's major key and its relative minor, which removes almost all
    of the usual ambiguity.
    """
    total = sum(profile)
    if total <= 0:
        return Key(tonic=0, mode='major', confidence=0.0)

    normalized = [p / total for p in profile]
    candidates = []
    for tonic in range(12):
        for mode, ref in (('major', MAJOR_PROFILE), ('minor', MINOR_PROFILE)):
            rotated = [ref[(i - tonic) % 12] for i in range(12)]
            candidates.append((_correlate(normalized, rotated), tonic, mode))
    candidates.sort(key=lambda c: -c[0])

    if key_sharps is not None:
        major_tonic = (key_sharps * 7) % 12
        minor_tonic = (major_tonic + 9) % 12
        allowed = {(major_tonic, 'major'), (minor_tonic, 'minor')}
        filtered = [c for c in candidates if (c[1], c[2]) in allowed]
        if filtered:
            candidates = filtered

    best = candidates[0]
    runner = candidates[1][0] if len(candidates) > 1 else 0.0
    confidence = max(0.0, min(1.0, (best[0] - runner) * 2.5 + 0.5))
    return Key(tonic=best[1], mode=best[2], confidence=confidence)


def _correlate(a: list, b: list) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((x - mb) ** 2 for x in b))
    return num / (da * db) if da > 0 and db > 0 else 0.0


# --------------------------------------------------------------------------
# Roman numerals, function, cadences
# --------------------------------------------------------------------------

def roman_numeral(root: int, quality: str, key: Key) -> str:
    semitone = (root - key.tonic) % 12
    table = DEGREE_OF_SEMITONE_MAJOR if key.mode == 'major' else DEGREE_OF_SEMITONE_MINOR
    degree, accidental = table[semitone]
    numeral = ROMAN[degree - 1]

    minorish = quality in ('minor', 'minor seventh', 'diminished', 'half-diminished',
                           'diminished seventh', 'minor sixth', 'minor ninth',
                           'minor-major seventh')
    if minorish:
        numeral = numeral.lower()

    text = f"{accidental}{numeral}"
    if quality == 'diminished':
        text += '°'
    elif quality == 'diminished seventh':
        text += '°7'
    elif quality == 'half-diminished':
        text += 'ø7'
    elif quality == 'augmented':
        text += '+'
    elif quality == 'dominant seventh':
        text += '7'
    elif quality == 'major seventh':
        text += 'maj7'
    elif quality == 'minor seventh':
        text += '7'
    elif quality in ('suspended fourth', 'suspended second'):
        text += 'sus'
    elif quality == 'sixth' or quality == 'minor sixth':
        text += '6'
    elif quality in ('dominant ninth', 'minor ninth', 'added ninth'):
        text += '9'
    elif quality == 'dominant seventh flat ninth':
        text += '7♭9'
    return text


DOMINANT_QUALITIES = ('dominant seventh', 'dominant ninth', 'dominant seventh flat ninth')


def secondary_dominant_target(root: int, quality: str, key: Key) -> Optional[str]:
    """
    If this chord acts as V of some other degree, name that degree.

    A dominant-quality chord that is not the key's own V is almost always
    tonicising the chord a fifth below it, which is the single most useful
    thing to tell someone reading the progression.
    """
    if quality not in DOMINANT_QUALITIES and quality != 'major':
        return None
    degree = (root - key.tonic) % 12
    if degree == 7:
        return None
    if quality == 'major' and degree in (0, 5):
        return None

    target = (root + 5) % 12
    target_degree = (target - key.tonic) % 12
    scale_degrees = {(pc - key.tonic) % 12 for pc in key.scale()}
    if target_degree not in scale_degrees or target_degree == 0:
        return None
    table = DEGREE_OF_SEMITONE_MAJOR if key.mode == 'major' else DEGREE_OF_SEMITONE_MINOR
    number, accidental = table[target_degree]
    numeral = ROMAN[number - 1]

    major_diatonic = {0: False, 2: True, 4: True, 5: False, 7: False, 9: True, 11: True}
    minor_diatonic = {0: True, 3: False, 5: True, 7: False, 8: False, 10: False, 2: True}
    lower = (major_diatonic if key.mode == 'major' else minor_diatonic).get(target_degree, False)
    if lower:
        numeral = numeral.lower()
    return f"{accidental}{numeral}"


MAJOR_TRIAD_QUALITIES = ('major', 'major seventh', 'sixth', 'added ninth',
                         'suspended second', 'suspended fourth')
MINOR_TRIAD_QUALITIES = ('minor', 'minor seventh', 'minor sixth', 'minor ninth',
                         'minor-major seventh', 'suspended second', 'suspended fourth')


def _quality_fits_degree(quality: str, semitone: int, mode: str) -> bool:
    """Whether this chord quality is the one the key builds on that degree."""
    if mode == 'major':
        expected = {0: MAJOR_TRIAD_QUALITIES, 2: MINOR_TRIAD_QUALITIES,
                    4: MINOR_TRIAD_QUALITIES, 5: MAJOR_TRIAD_QUALITIES,
                    7: MAJOR_TRIAD_QUALITIES + ('dominant seventh', 'dominant ninth',
                                                'dominant seventh flat ninth'),
                    9: MINOR_TRIAD_QUALITIES,
                    11: ('diminished', 'half-diminished', 'diminished seventh')}
    else:
        expected = {0: MINOR_TRIAD_QUALITIES, 2: ('diminished', 'half-diminished',
                                                  'diminished seventh'),
                    3: MAJOR_TRIAD_QUALITIES, 5: MINOR_TRIAD_QUALITIES,
                    7: MINOR_TRIAD_QUALITIES + MAJOR_TRIAD_QUALITIES + (
                        'dominant seventh', 'dominant ninth',
                        'dominant seventh flat ninth'),
                    8: MAJOR_TRIAD_QUALITIES, 10: MAJOR_TRIAD_QUALITIES,
                    11: ('diminished', 'half-diminished', 'diminished seventh')}
    return quality in expected.get(semitone, ())


def harmonic_function(root: int, quality: str, key: Key) -> str:
    semitone = (root - key.tonic) % 12
    if key.mode == 'major':
        mapping = {0: 'tonic', 9: 'tonic', 4: 'tonic',
                   5: 'subdominant', 2: 'subdominant',
                   7: 'dominant', 11: 'dominant'}
    else:
        mapping = {0: 'tonic', 3: 'tonic', 8: 'tonic',
                   5: 'subdominant', 2: 'subdominant', 10: 'subdominant',
                   7: 'dominant', 11: 'dominant'}
    base = mapping.get(semitone)
    if base is None:
        return 'chromatic'
    # A seventh chord on the fifth degree is unambiguously dominant.
    if semitone == 7 and quality in DOMINANT_QUALITIES:
        return 'dominant'
    # Right root, wrong quality: the chord is borrowed, so it no longer does
    # the job that degree normally does.
    if not _quality_fits_degree(quality, semitone, key.mode):
        return 'chromatic'
    return base


def find_cadences(spans: list, keys: list, beats_per_measure: float = 4.0) -> list:
    """
    Label cadences where a phrase actually comes to rest.

    A V-I in the middle of a bar is ordinary chord motion, not a cadence.
    What makes it one is arrival: the resolution lands on a downbeat, in a
    new measure, and is given room to settle.
    """
    cadences = []
    for i in range(1, len(spans)):
        prev, curr = spans[i - 1], spans[i]
        if curr.beat > 0.01 or curr.measure_index == prev.measure_index:
            continue
        settled = curr.beats >= beats_per_measure * 0.49

        key = keys[curr.key_index] if keys else Key(0, 'major')
        a = (prev.root - key.tonic) % 12
        b = (curr.root - key.tonic) % 12

        label = None
        if a == 7 and b == 0:
            label = 'Perfect cadence' if curr.inversion == 0 else 'Imperfect cadence'
        elif a == 7 and b == 9 and key.mode == 'major':
            label = 'Deceptive cadence'
        elif a == 7 and b == 8 and key.mode == 'minor':
            label = 'Deceptive cadence'
        elif a == 5 and b == 0:
            label = 'Plagal cadence'
        elif b == 7 and a in (0, 2, 5, 9) and settled:
            label = 'Half cadence'

        if label is None:
            continue
        progression = None
        if i >= 2:
            before = (spans[i - 2].root - key.tonic) % 12
            if before == 2 and a == 7 and b == 0:
                progression = 'ii - V - I'
            elif before == 9 and a == 2 and b == 7:
                progression = 'vi - ii - V'
        cadences.append({
            'index': i,
            'label': label,
            'progression': progression,
            'measure': curr.measure_index,
        })
    return cadences


# --------------------------------------------------------------------------
# Main analysis
# --------------------------------------------------------------------------

def _segment_measure(measure, space: float, divisions: int) -> list:
    """
    Split a measure into `divisions` beat slots of onsets.

    Engravers space notes in proportion to their duration, so horizontal
    position within the bar stands in for time. Slots keep their index even
    when empty, so a chord that starts on beat three is not mistaken for one
    on beat one.
    """
    onsets = group_onsets(measure.noteheads, space)
    if not onsets:
        return []
    width = measure.x2 - measure.x1
    if width <= 0 or divisions <= 1:
        return [(0, onsets)]

    buckets = [[] for _ in range(divisions)]
    for group in onsets:
        cx = sum(n.cx for n in group) / len(group)
        idx = int((cx - measure.x1) / width * divisions)
        buckets[min(divisions - 1, max(0, idx))].append(group)
    return [(slot, groups) for slot, groups in enumerate(buckets) if groups]


def _chord_pitch_classes(root: int, quality: str) -> list:
    for name, _, intervals, _, _ in CHORD_TEMPLATES:
        if name == quality:
            return sorted({(root + i) % 12 for i in intervals})
    return []


def meter_divisions(time_signature: Optional[tuple]) -> tuple:
    """
    How many chords a measure may be split into, and how long each beat is.

    Harmony changes on beats, so the candidate splits are the ones the meter
    actually allows: a 3/4 bar can hold one or three chords but not two, and
    a 6/8 bar has two dotted beats rather than six.
    """
    if not time_signature:
        return (1, 2, 4), 4.0
    numerator, denominator = time_signature
    if denominator == 8 and numerator % 3 == 0 and numerator > 3:
        beats = numerator // 3
    else:
        beats = numerator
    options = [1] + [d for d in (2, 3, 4) if d <= beats and beats % d == 0]
    return tuple(dict.fromkeys(options)), float(beats)


def _span_from_groups(groups: list, measure, space: float, divisions: int, slot: int,
                      key: Optional[Key], beats_per_measure: float, top_k: int = 6):
    notes = [n for g in groups for n in g]
    if not notes:
        return None
    profile = profile_from_notes(notes)
    pitched = [n for n in notes if n.midi]
    lowest = min(pitched, key=lambda n: n.midi) if pitched else None
    bass = lowest.midi if lowest is not None else None
    candidates = score_chord(profile, bass % 12 if bass is not None else None, key)
    if not candidates:
        return None
    candidates = candidates[:top_k]

    width = measure.x2 - measure.x1
    x1 = min(n.x1 for n in notes)
    x2 = max(n.x2 for n in notes)
    if divisions > 1:
        x1 = min(x1, measure.x1 + width * slot / divisions)
        x2 = max(x2, measure.x1 + width * (slot + 1) / divisions)
    else:
        x1, x2 = measure.x1, measure.x2

    span = ChordSpan(
        measure_index=measure.index,
        system_index=measure.system_index,
        beat=slot * beats_per_measure / divisions,
        beats=beats_per_measure / divisions,
        x1=float(x1), x2=float(x2),
        root=candidates[0][1], quality=candidates[0][2], suffix=candidates[0][3],
        confidence=0.5,
        pitch_classes=[],
        note_ids=[id(n) for n in notes],
        bass=bass,
        bass_name=(lowest.name.rstrip('-0123456789') or None) if lowest is not None else None,
        prefers_sharps=key.prefers_sharps if key is not None else True,
    )
    span.notes = notes
    return span, candidates[0][0], candidates


def finalize_span(span: ChordSpan, candidates: list, chosen: int) -> None:
    """Apply the decoded chord choice and derive confidence from the margin."""
    score, root, quality, suffix = candidates[chosen]
    span.root, span.quality, span.suffix = root, quality, suffix
    span.pitch_classes = _chord_pitch_classes(root, quality)

    best = candidates[0][0]
    runner = candidates[1][0] if len(candidates) > 1 else best - 0.5
    margin = best - runner
    distinct = len({n.midi % 12 for n in getattr(span, 'notes', []) if n.midi})
    confidence = 0.32 + margin * 1.5 + min(distinct, 4) * 0.09
    if chosen != 0:
        confidence -= 0.12
    span.confidence = max(0.05, min(1.0, confidence))

    if span.bass is not None and span.pitch_classes:
        interval = (span.bass % 12 - root) % 12
        span.inversion = {0: 0, 4: 1, 3: 1, 7: 2, 10: 3, 11: 3}.get(interval, 0)


def _onset_pitch_classes(group: list) -> set:
    return {n.midi % 12 for n in group if n.midi}


def _onset_bass(group: list) -> Optional[int]:
    pitched = [n.midi for n in group if n.midi]
    return min(pitched) if pitched else None


def _should_split_onsets(current: list, nxt: list, key: Optional[Key],
                         already: int, soft_cap: int) -> bool:
    """
    Whether the next onset starts a new chord rather than decorating this one.

    Printed Jobim guitar charts usually change once mid-bar. Walking basses and
    inner-voice motion look like new chords if the bar is too eager to split,
    so the second change in a bar needs stronger evidence than the first.
    """
    cur_notes = [n for g in current for n in g]
    nxt_pcs = _onset_pitch_classes(nxt)
    cur_pcs = {n.midi % 12 for n in cur_notes if n.midi}
    if not nxt_pcs or not cur_pcs:
        return False

    new_tones = nxt_pcs - cur_pcs
    shared = nxt_pcs & cur_pcs
    if not new_tones:
        return False

    # Need a real vertical event, not a single melody note.
    if len(nxt_pcs) < 2 and len(nxt) < 2:
        return False

    cur_bass = _onset_bass(cur_notes)
    nxt_bass = _onset_bass(nxt)
    bass_moved = (
        cur_bass is not None and nxt_bass is not None
        and (cur_bass % 12) != (nxt_bass % 12)
        and abs(nxt_bass - cur_bass) >= 3
    )

    alone = score_chord(profile_from_notes(cur_notes),
                        cur_bass % 12 if cur_bass is not None else None, key)
    merged_notes = cur_notes + list(nxt)
    merged_bass = min(n.midi for n in merged_notes if n.midi)
    merged = score_chord(profile_from_notes(merged_notes), merged_bass % 12, key)
    alone_score = alone[0][0] if alone else 0.0
    merged_score = merged[0][0] if merged else 0.0
    alone_root = alone[0][1] if alone else None
    merged_root = merged[0][1] if merged else None
    drop = alone_score - merged_score
    root_changed = alone_root is not None and alone_root != merged_root

    # After the usual half-bar change, demand a clearer break.
    threshold = 0.16 if already >= soft_cap else 0.09
    if bass_moved and root_changed and drop > threshold - 0.03:
        return True
    if len(new_tones) >= 2 and root_changed and drop > threshold:
        return True
    if len(new_tones) >= 2 and len(shared) <= 1 and drop > threshold + 0.02:
        return True
    if already < soft_cap and bass_moved and len(new_tones) >= 1 and drop > 0.08:
        return True
    return False


def choose_harmonic_rhythm(measure, space: float, key: Optional[Key],
                           options: tuple = (1, 2, 4),
                           beats_per_measure: float = 4.0) -> list:
    """
    Segment a measure by musical onsets, not equal-width slices.

    Equal beat buckets hide half-bar changes that guitar charts print above
    the staff. Onsets are walked left to right; a new chord starts when the
    bass and pitch-class content stop fitting the chord already under way.
    Meter still caps how many chords a bar may hold.
    """
    onsets = group_onsets(measure.noteheads, space)
    if not onsets:
        return []

    max_chords = max(options) if options else 4
    # Guitar charts of this repertoire almost always change once per bar;
    # allow more only when the evidence is strong.
    soft_cap = 2 if beats_per_measure >= 3 else 2
    segments: list = [[onsets[0]]]
    for group in onsets[1:]:
        if len(segments) >= max_chords:
            segments[-1].append(group)
            continue
        if _should_split_onsets(segments[-1], group, key, len(segments), soft_cap):
            segments.append([group])
        else:
            segments[-1].append(group)

    # Assign each segment a beat slot from its horizontal centre so the
    # ribbon still knows where in the bar the change landed.
    width = max(1e-6, measure.x2 - measure.x1)
    entries = []
    for groups in segments:
        notes = [n for g in groups for n in g]
        cx = sum(n.cx for n in notes) / len(notes)
        slot = int((cx - measure.x1) / width * max(1, int(beats_per_measure)))
        slot = min(max(0, slot), max(0, int(beats_per_measure) - 1))
        made = _span_from_groups(groups, measure, space, max(1, int(beats_per_measure)),
                                 slot, key, beats_per_measure)
        if made is None:
            continue
        span, _raw, candidates = made
        # Duration: from this segment's left edge to the next, or the bar end.
        span.x1 = float(min(n.x1 for n in notes))
        span.x2 = float(max(n.x2 for n in notes))
        entries.append((span, candidates))

    if not entries:
        return []

    # Stretch each span to meet its neighbour so the overlay has no gaps.
    for index, (span, _) in enumerate(entries):
        left = measure.x1 if index == 0 else (entries[index - 1][0].x2 + span.x1) / 2
        right = measure.x2 if index == len(entries) - 1 else (span.x2 + entries[index + 1][0].x1) / 2
        span.x1, span.x2 = float(left), float(right)
        span.beats = max(0.5, beats_per_measure / len(entries))
        span.beat = index * span.beats

    return entries


def _merge_repeats(spans: list) -> list:
    merged = []
    for span in spans:
        if (merged and merged[-1].root == span.root and merged[-1].quality == span.quality
                and merged[-1].measure_index == span.measure_index):
            prev = merged[-1]
            prev.x2 = max(prev.x2, span.x2)
            prev.beats += span.beats
            prev.note_ids.extend(span.note_ids)
            prev.confidence = max(prev.confidence, span.confidence)
            continue
        merged.append(span)
    return merged


def _transition_cost(a: tuple, b: tuple, key: Key) -> float:
    """
    Cost of following chord `a` with chord `b`.

    Encodes ordinary tonal behaviour: repeating a chord is free, root motion
    by fifth or step is cheap, and a leap to an unrelated chromatic root is
    expensive.
    """
    root_a, quality_a = a
    root_b, quality_b = b
    if root_a == root_b and quality_a == quality_b:
        return 0.0

    interval = (root_b - root_a) % 12
    cost = {
        0: 0.10,   # same root, different quality
        5: 0.02,   # down a fifth
        7: 0.05,   # up a fifth
        2: 0.10, 10: 0.10,   # step
        9: 0.12, 3: 0.12,    # thirds
        4: 0.14, 8: 0.14,
    }.get(interval, 0.22)

    scale = set(key.scale())
    if root_b % 12 not in scale:
        cost += 0.10
    # A dominant that resolves down a fifth is idiomatic, not a surprise.
    if quality_a in ('dominant seventh', 'dominant ninth', 'dominant seventh flat ninth') \
            and interval == 5:
        cost -= 0.08
    return max(0.0, cost)


def smooth_sequence(candidates: list, key: Key, weight: float = 1.0) -> list:
    """
    Viterbi decode over per-segment chord candidates.

    Without this a single misread notehead invents a chord change; the
    transition model prefers holding a chord, moving by fifths and staying
    inside the key, so isolated oddities get outvoted by their neighbours.
    """
    if not candidates:
        return []
    if len(candidates) == 1:
        return [0]

    n = len(candidates)
    best = [[0.0] * len(c) for c in candidates]
    back = [[0] * len(c) for c in candidates]
    for j, (score, root, name, suffix) in enumerate(candidates[0]):
        best[0][j] = score

    for i in range(1, n):
        for j, (score, root, name, suffix) in enumerate(candidates[i]):
            top, arg = -1e18, 0
            for k, (_, proot, pname, _) in enumerate(candidates[i - 1]):
                value = best[i - 1][k] - weight * _transition_cost(
                    (proot, pname), (root, name), key)
                if value > top:
                    top, arg = value, k
            best[i][j] = score + top
            back[i][j] = arg

    path = [0] * n
    path[n - 1] = int(max(range(len(candidates[n - 1])), key=lambda j: best[n - 1][j]))
    for i in range(n - 1, 0, -1):
        path[i - 1] = back[i][path[i]]
    return path


def _page_key_signature(geo) -> Optional[int]:
    votes = {}
    for system in geo.systems:
        for staff in system.staves:
            votes[staff.key_sharps] = votes.get(staff.key_sharps, 0) + 1
    if not votes:
        return None
    return max(votes.items(), key=lambda kv: (kv[1], -abs(kv[0])))[0]


def _key_for_notes(noteheads: list, key_sharps: Optional[int] = None) -> Key:
    profile = [0.0] * 12
    for pc, weight in enumerate(profile_from_notes(noteheads)):
        profile[pc] += weight
    return detect_key(profile, key_sharps)


def _keys_compatible(a: Optional[Key], b: Optional[Key]) -> bool:
    """Same key, or relative major/minor — keep them as one section."""
    if a is None or b is None:
        return False
    if a.tonic == b.tonic and a.mode == b.mode:
        return True
    if a.mode == 'major' and b.mode == 'minor' and b.tonic == (a.tonic + 9) % 12:
        return True
    if a.mode == 'minor' and b.mode == 'major' and a.tonic == (b.tonic + 9) % 12:
        return True
    return False


def segment_keys(pages: list) -> list:
    """
    Split a book into local keys.

    Scanned songbooks misread key signatures often, so the pitch profile of
    each page decides the key. Adjacent pages stay in one section unless the
    new key persists for two pages in a row — a one-page blip is noise, not a
    modulation.
    """
    page_infos = []
    for entry in pages:
        geo = entry['geometry']
        notes = geo.noteheads
        # Signature is only a soft hint: hard-filtering by a wrong signature
        # is how a D-minor bossa ends up labelled A major.
        free = _key_for_notes(notes, None) if notes else None
        sharps = _page_key_signature(geo)
        hinted = _key_for_notes(notes, sharps) if notes and sharps is not None else free
        key = free
        if hinted is not None and free is not None:
            if (hinted.tonic, hinted.mode) == (free.tonic, free.mode):
                key = hinted
            elif hinted.confidence > free.confidence + 0.25:
                key = hinted
        page_infos.append({
            'page': entry['page'],
            'geo': geo,
            'key': key,
            'empty': not notes or not geo.measures,
        })

    sections = []
    current = None
    pending = None  # a disagreeing page waiting for confirmation
    for info in page_infos:
        if info['empty']:
            if pending is not None and current is not None:
                current['pages'].append(pending)
                pending = None
            if current is not None:
                notes = [n for p in current['pages'] for n in p['geo'].noteheads]
                current['key'] = _key_for_notes(notes, None) if notes else current['key']
                sections.append(current)
                current = None
            continue

        if current is None:
            current = {'pages': [info], 'key': info['key']}
            continue

        if _keys_compatible(current['key'], info['key']):
            if pending is not None:
                current['pages'].append(pending)
                pending = None
            current['pages'].append(info)
            notes = [n for p in current['pages'] for n in p['geo'].noteheads]
            current['key'] = _key_for_notes(notes, None)
            continue

        # First disagreeing page: hold it. A second one confirms a new section.
        if pending is None:
            pending = info
            continue

        if _keys_compatible(pending['key'], info['key']):
            notes = [n for p in current['pages'] for n in p['geo'].noteheads]
            current['key'] = _key_for_notes(notes, None) if notes else current['key']
            sections.append(current)
            current = {'pages': [pending, info], 'key': info['key']}
            notes = [n for p in current['pages'] for n in p['geo'].noteheads]
            current['key'] = _key_for_notes(notes, None)
            pending = None
        else:
            # Pending was a blip; absorb it and reconsider the new page.
            current['pages'].append(pending)
            notes = [n for p in current['pages'] for n in p['geo'].noteheads]
            current['key'] = _key_for_notes(notes, None)
            pending = info

    if pending is not None and current is not None:
        current['pages'].append(pending)
    if current is not None:
        notes = [n for p in current['pages'] for n in p['geo'].noteheads]
        current['key'] = _key_for_notes(notes, None) if notes else current['key']
        sections.append(current)
    return sections


def analyze(pages: list) -> dict:
    """
    Run the harmony engine across pages of geometry.

    `pages` is a list of dicts: {'geometry': PageGeometry, 'page': int}.
    """
    sections = segment_keys(pages)
    if not sections:
        empty_key = Key(0, 'major', 0.0)
        return {
            'key': empty_key,
            'keys': [empty_key],
            'spans': [],
            'cadences': [],
            'profile': [0.0] * 12,
            'time_signature': None,
            'beats_per_measure': 4.0,
        }

    keys = []
    merged = []
    global_profile = [0.0] * 12
    meter_votes = {}

    for section in sections:
        key = section['key'] or Key(0, 'major', 0.0)
        key_index = len(keys)
        keys.append(key)

        all_measures = []
        for info in section['pages']:
            geo = info['geo']
            for measure in sorted(geo.measures, key=lambda m: m.index):
                all_measures.append((info['page'], geo, measure))
                for pc, weight in enumerate(profile_from_notes(measure.noteheads)):
                    global_profile[pc] += weight

        meter_at = {}
        current_meter = None
        for position, (page, geo, measure) in enumerate(all_measures):
            for start, meter in getattr(geo, 'meter_changes', []):
                if start == measure.index:
                    current_meter = meter
            meter_at[position] = current_meter
            if current_meter:
                meter_votes[current_meter] = meter_votes.get(current_meter, 0) + 1

        entries = []
        for position, (page, geo, measure) in enumerate(all_measures):
            options, beats = meter_divisions(meter_at[position])
            for span, candidates in choose_harmonic_rhythm(
                    measure, geo.space, key, options, beats):
                span.key_index = key_index
                span.prefers_sharps = key.prefers_sharps
                entries.append((page, span, candidates))

        path = smooth_sequence([c for _, _, c in entries], key)
        for (page, span, candidates), chosen in zip(entries, path):
            finalize_span(span, candidates, chosen)

        for page, span, _ in entries:
            if (merged and merged[-1][1].measure_index == span.measure_index
                    and merged[-1][0] == page
                    and merged[-1][1].root == span.root
                    and merged[-1][1].quality == span.quality):
                prev = merged[-1][1]
                prev.x2 = max(prev.x2, span.x2)
                prev.beats += span.beats
                prev.confidence = max(prev.confidence, span.confidence)
                prev.note_ids.extend(span.note_ids)
                continue
            merged.append((page, span))

    time_signature = (
        max(meter_votes.items(), key=lambda kv: kv[1])[0] if meter_votes else None
    )
    _, beats_per_measure = meter_divisions(time_signature)

    for _, span in merged:
        key = keys[span.key_index]
        span.roman = roman_numeral(span.root, span.quality, key)
        span.function = harmonic_function(span.root, span.quality, key)
        target = secondary_dominant_target(span.root, span.quality, key)
        if target and target != 'I':
            span.roman = f'V/{target}'
            span.function = 'secondary-dominant'
            span.tonicizes = target

    # Cadences are labelled inside each key section so a key change itself is
    # not mistaken for a deceptive cadence.
    cadences = []
    by_key = {}
    for index, (page, span) in enumerate(merged):
        by_key.setdefault(span.key_index, []).append((index, span))
    for key_index, items in by_key.items():
        local_spans = [span for _, span in items]
        local = find_cadences(local_spans, keys, beats_per_measure)
        for cadence in local:
            # find_cadences indexes into the local list; map back.
            global_index = items[cadence['index']][0]
            cadences.append({
                'index': global_index,
                'label': cadence['label'],
                'progression': cadence['progression'],
                'measure': cadence['measure'],
            })
    cadences.sort(key=lambda c: c['index'])

    # The headline key is the section with the most music, not the first page.
    headline = max(
        range(len(keys)),
        key=lambda i: sum(1 for _, span in merged if span.key_index == i),
        default=0,
    )
    return {
        'key': keys[headline],
        'keys': keys,
        'spans': merged,
        'cadences': cadences,
        'profile': global_profile,
        'time_signature': time_signature,
        'beats_per_measure': beats_per_measure,
    }
