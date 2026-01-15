"""
Music theory utilities.

Constants and helper functions for music theory operations.
"""

# Note names in chromatic order
CHROMATIC_NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Enharmonic equivalents
ENHARMONIC = {
    'Db': 'C#', 'Eb': 'D#', 'Fb': 'E', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#', 'Cb': 'B',
    'E#': 'F', 'B#': 'C',
}

# Interval names
INTERVALS = {
    0: 'unison',
    1: 'minor 2nd',
    2: 'major 2nd',
    3: 'minor 3rd',
    4: 'major 3rd',
    5: 'perfect 4th',
    6: 'tritone',
    7: 'perfect 5th',
    8: 'minor 6th',
    9: 'major 6th',
    10: 'minor 7th',
    11: 'major 7th',
}

# Chord quality intervals
CHORD_INTERVALS = {
    'major': [0, 4, 7],
    'minor': [0, 3, 7],
    'diminished': [0, 3, 6],
    'augmented': [0, 4, 8],
    'major7': [0, 4, 7, 11],
    'minor7': [0, 3, 7, 10],
    'dominant7': [0, 4, 7, 10],
    'diminished7': [0, 3, 6, 9],
    'half-diminished7': [0, 3, 6, 10],
    'sus2': [0, 2, 7],
    'sus4': [0, 5, 7],
}

# Scale degrees for major key
MAJOR_SCALE_DEGREES = [0, 2, 4, 5, 7, 9, 11]

# Scale degrees for natural minor key
MINOR_SCALE_DEGREES = [0, 2, 3, 5, 7, 8, 10]

# Roman numerals
ROMAN_NUMERALS = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII']

# Common chord progressions and their names
COMMON_PROGRESSIONS = {
    ('I', 'V', 'vi', 'IV'): 'Pop progression',
    ('I', 'IV', 'V', 'I'): 'Classical cadence',
    ('ii', 'V', 'I'): 'Jazz ii-V-I',
    ('I', 'vi', 'IV', 'V'): '50s progression',
    ('I', 'IV', 'I', 'V'): '12-bar blues (simplified)',
    ('vi', 'IV', 'I', 'V'): 'Axis progression',
    ('I', 'V', 'vi', 'iii', 'IV'): 'Canon progression',
}


def normalize_note(note: str) -> str:
    """Convert a note to its canonical form (using sharps)."""
    if note in ENHARMONIC:
        return ENHARMONIC[note]
    return note


def note_to_midi(note: str, octave: int = 4) -> int:
    """Convert note name and octave to MIDI number."""
    note = normalize_note(note)
    if note in CHROMATIC_NOTES:
        return CHROMATIC_NOTES.index(note) + (octave + 1) * 12
    return 60  # Default to middle C


def midi_to_note(midi: int) -> tuple:
    """Convert MIDI number to (note name, octave)."""
    octave = (midi // 12) - 1
    note_idx = midi % 12
    return CHROMATIC_NOTES[note_idx], octave


def get_interval(note1: str, note2: str) -> int:
    """Get interval in semitones between two notes."""
    n1 = normalize_note(note1)
    n2 = normalize_note(note2)

    if n1 not in CHROMATIC_NOTES or n2 not in CHROMATIC_NOTES:
        return 0

    idx1 = CHROMATIC_NOTES.index(n1)
    idx2 = CHROMATIC_NOTES.index(n2)

    return (idx2 - idx1) % 12


def get_chord_quality(intervals: list) -> str:
    """Determine chord quality from intervals."""
    intervals = sorted(set(intervals))

    for quality, template in CHORD_INTERVALS.items():
        if intervals == template:
            return quality

    # Check partial matches
    if 0 in intervals and 4 in intervals and 7 in intervals:
        if 11 in intervals:
            return 'major7'
        if 10 in intervals:
            return 'dominant7'
        return 'major'

    if 0 in intervals and 3 in intervals and 7 in intervals:
        if 10 in intervals:
            return 'minor7'
        return 'minor'

    return 'unknown'


def identify_progression(roman_numerals: list) -> str:
    """Identify a common chord progression by name."""
    # Normalize and convert to tuple for lookup
    normalized = tuple(r.replace('7', '').replace('maj', '') for r in roman_numerals[:5])

    for pattern, name in COMMON_PROGRESSIONS.items():
        if normalized[:len(pattern)] == pattern:
            return name

    return None


def get_key_signature_notes(key_tonic: str, mode: str = 'major') -> list:
    """Get the notes in a key signature."""
    tonic = normalize_note(key_tonic)
    if tonic not in CHROMATIC_NOTES:
        tonic = 'C'

    tonic_idx = CHROMATIC_NOTES.index(tonic)
    degrees = MAJOR_SCALE_DEGREES if mode == 'major' else MINOR_SCALE_DEGREES

    return [CHROMATIC_NOTES[(tonic_idx + d) % 12] for d in degrees]


def analyze_chord_function(roman: str, key_mode: str = 'major') -> dict:
    """
    Analyze the harmonic function of a chord.

    Returns function, tendency, and common next chords.
    """
    base = roman.upper().replace('7', '').replace('MAJ', '').replace('DIM', '').replace('AUG', '')

    functions = {
        'I': {
            'function': 'tonic',
            'tendency': 'stable',
            'common_next': ['IV', 'V', 'vi', 'ii'],
            'description': 'Home chord. Creates stability and resolution.',
        },
        'II': {
            'function': 'predominant',
            'tendency': 'moves to V',
            'common_next': ['V', 'vii°'],
            'description': 'Supertonic. Creates motion toward dominant.',
        },
        'III': {
            'function': 'tonic',
            'tendency': 'stable (substitute)',
            'common_next': ['IV', 'vi'],
            'description': 'Mediant. Can substitute for tonic.',
        },
        'IV': {
            'function': 'predominant',
            'tendency': 'moves to V or I',
            'common_next': ['V', 'I', 'ii'],
            'description': 'Subdominant. Strong predominant function.',
        },
        'V': {
            'function': 'dominant',
            'tendency': 'resolves to I',
            'common_next': ['I', 'vi'],
            'description': 'Dominant. Creates tension wanting resolution.',
        },
        'VI': {
            'function': 'tonic',
            'tendency': 'stable (substitute)',
            'common_next': ['IV', 'ii', 'V'],
            'description': 'Submediant. Deceptive resolution target.',
        },
        'VII': {
            'function': 'dominant',
            'tendency': 'resolves to I',
            'common_next': ['I', 'iii'],
            'description': 'Leading tone chord. Strong pull to tonic.',
        },
    }

    if base in functions:
        return functions[base]

    return {
        'function': 'unknown',
        'tendency': 'context-dependent',
        'common_next': [],
        'description': 'Chord function could not be determined.',
    }
