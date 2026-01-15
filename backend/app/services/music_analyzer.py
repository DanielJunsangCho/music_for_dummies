"""
Music analysis service.

Performs chord detection, key analysis, and harmonic function classification.
Uses music21 for music theory operations when available.
"""

import os
import json
import uuid
import asyncio
from typing import AsyncGenerator

# Try to import music21
try:
    from music21 import chord, key, roman, pitch, scale
    HAS_MUSIC21 = True
except ImportError:
    HAS_MUSIC21 = False


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")

# Chord function mappings
CHORD_FUNCTIONS = {
    'I': 'tonic',
    'i': 'tonic',
    'III': 'tonic',
    'iii': 'tonic',
    'VI': 'tonic',
    'vi': 'tonic',
    'II': 'predominant',
    'ii': 'predominant',
    'IV': 'predominant',
    'iv': 'predominant',
    'V': 'dominant',
    'v': 'dominant',
    'VII': 'dominant',
    'vii': 'dominant',
}


def get_chord_function(roman_numeral: str) -> str:
    """Determine harmonic function from Roman numeral."""
    # Strip any extensions (7, maj7, etc.) and accidentals
    base = roman_numeral.replace('7', '').replace('maj', '').replace('dim', '').replace('aug', '')
    base = base.replace('#', '').replace('b', '').replace('+', '').replace('°', '')

    if base in CHORD_FUNCTIONS:
        return CHORD_FUNCTIONS[base]

    # Check for secondary dominants
    if '/' in roman_numeral:
        return 'secondary_dominant'

    # Borrowed chords (e.g., bVII, bIII)
    if roman_numeral.startswith('b') or roman_numeral.startswith('#'):
        return 'borrowed'

    return 'unknown'


def analyze_chord_symbol(symbol: str, current_key: str = 'C') -> dict:
    """
    Analyze a chord symbol and return detailed information.

    Args:
        symbol: Chord symbol (e.g., "Cmaj7", "Am", "D7/F#")
        current_key: Current key context

    Returns:
        dict with chord analysis
    """
    if HAS_MUSIC21:
        return _analyze_with_music21(symbol, current_key)
    else:
        return _analyze_basic(symbol, current_key)


def _analyze_with_music21(symbol: str, current_key: str) -> dict:
    """Use music21 for chord analysis."""
    try:
        # Parse the chord
        c = chord.Chord(symbol)
        k = key.Key(current_key)

        # Get Roman numeral
        rn = roman.romanNumeralFromChord(c, k)

        return {
            "symbol": symbol,
            "root": c.root().name if c.root() else symbol[0],
            "quality": c.quality,
            "notes": [p.name for p in c.pitches],
            "romanNumeral": rn.romanNumeral,
            "function": get_chord_function(rn.romanNumeral),
        }
    except Exception:
        return _analyze_basic(symbol, current_key)


def _analyze_basic(symbol: str, current_key: str) -> dict:
    """Basic chord analysis without music21."""
    # Parse chord symbol
    root = symbol[0].upper()
    if len(symbol) > 1 and symbol[1] in ['#', 'b']:
        root += symbol[1]
        quality_part = symbol[2:]
    else:
        quality_part = symbol[1:] if len(symbol) > 1 else ''

    # Handle slash chords
    bass = None
    if '/' in quality_part:
        parts = quality_part.split('/')
        quality_part = parts[0]
        bass = parts[1]

    # Determine quality
    quality = 'major'
    if 'm' in quality_part.lower() and 'maj' not in quality_part.lower():
        quality = 'minor'
    elif 'dim' in quality_part.lower() or '°' in quality_part:
        quality = 'diminished'
    elif 'aug' in quality_part.lower() or '+' in quality_part:
        quality = 'augmented'

    # Calculate notes based on root and quality
    notes = _get_chord_notes(root, quality_part)

    # Calculate Roman numeral
    roman_numeral = _get_roman_numeral(root, quality, current_key)

    return {
        "symbol": symbol,
        "root": root,
        "quality": quality_part if quality_part else 'maj',
        "bass": bass,
        "notes": notes,
        "romanNumeral": roman_numeral,
        "function": get_chord_function(roman_numeral),
    }


def _get_chord_notes(root: str, quality: str) -> list:
    """Get notes in a chord based on root and quality."""
    # Simplified note calculation
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    # Handle flats
    flat_to_sharp = {'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'}
    if root in flat_to_sharp:
        root = flat_to_sharp[root]

    if root not in note_names:
        root = root[0]  # Fallback to just the letter

    root_idx = note_names.index(root) if root in note_names else 0

    # Intervals based on quality
    if 'm' in quality and 'maj' not in quality:
        intervals = [0, 3, 7]  # Minor
    elif 'dim' in quality or '°' in quality:
        intervals = [0, 3, 6]  # Diminished
    elif 'aug' in quality or '+' in quality:
        intervals = [0, 4, 8]  # Augmented
    else:
        intervals = [0, 4, 7]  # Major

    # Add 7th if present
    if '7' in quality:
        if 'maj7' in quality.lower():
            intervals.append(11)  # Major 7th
        else:
            intervals.append(10)  # Minor 7th

    notes = []
    for interval in intervals:
        note_idx = (root_idx + interval) % 12
        notes.append(note_names[note_idx])

    return notes


def _get_roman_numeral(root: str, quality: str, key_tonic: str) -> str:
    """Calculate Roman numeral relative to key."""
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    roman_numerals = ['I', 'bII', 'II', 'bIII', 'III', 'IV', '#IV', 'V', 'bVI', 'VI', 'bVII', 'VII']

    # Normalize flats
    flat_to_sharp = {'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'}
    if root in flat_to_sharp:
        root = flat_to_sharp[root]
    if key_tonic in flat_to_sharp:
        key_tonic = flat_to_sharp[key_tonic]

    root_idx = note_names.index(root) if root in note_names else 0
    key_idx = note_names.index(key_tonic) if key_tonic in note_names else 0

    degree = (root_idx - key_idx) % 12
    numeral = roman_numerals[degree]

    # Lowercase for minor chords
    if quality == 'minor' or quality == 'm':
        numeral = numeral.lower()

    return numeral


async def get_analysis_result(file_id: str) -> dict:
    """
    Get or generate analysis result for a file.
    """
    upload_path = os.path.join(UPLOAD_DIR, file_id)
    analysis_path = os.path.join(upload_path, "analysis.json")

    # Check for cached analysis
    if os.path.exists(analysis_path):
        with open(analysis_path, 'r') as f:
            return json.load(f)

    # Generate mock analysis
    result = generate_mock_analysis(file_id)

    # Cache the result
    with open(analysis_path, 'w') as f:
        json.dump(result, f)

    return result


async def analyze_music(file_id: str) -> AsyncGenerator[dict, None]:
    """
    Analyze music with progress updates.

    Yields progress updates and final result.
    """
    upload_path = os.path.join(UPLOAD_DIR, file_id)

    # Simulate analysis steps
    steps = [
        (0.1, "Loading PDF..."),
        (0.2, "Detecting staves..."),
        (0.4, "Recognizing notes..."),
        (0.6, "Detecting chords..."),
        (0.8, "Analyzing harmony..."),
        (0.9, "Detecting key changes..."),
    ]

    for progress, message in steps:
        yield {"type": "progress", "value": progress, "message": message}
        await asyncio.sleep(0.5)  # Simulate processing time

    # Generate final result
    result = generate_mock_analysis(file_id)

    # Save analysis
    analysis_path = os.path.join(upload_path, "analysis.json")
    with open(analysis_path, 'w') as f:
        json.dump(result, f)

    yield {"type": "progress", "value": 1.0, "message": "Complete"}
    yield {"type": "complete", "result": result}


def generate_mock_analysis(file_id: str) -> dict:
    """
    Generate mock analysis data with realistic chord progressions.

    This simulates what real OMR + analysis would produce.
    """
    global_key = {"tonic": "C", "mode": "major", "signature": 0}

    # Common chord progressions
    progressions = [
        # I - V - vi - IV (Pop progression)
        [
            {"symbol": "C", "root": "C", "quality": "maj", "notes": ["C", "E", "G"], "roman": "I", "func": "tonic"},
            {"symbol": "G", "root": "G", "quality": "maj", "notes": ["G", "B", "D"], "roman": "V", "func": "dominant"},
            {"symbol": "Am", "root": "A", "quality": "m", "notes": ["A", "C", "E"], "roman": "vi", "func": "tonic"},
            {"symbol": "F", "root": "F", "quality": "maj", "notes": ["F", "A", "C"], "roman": "IV", "func": "predominant"},
        ],
        # I - IV - V - I (Classic)
        [
            {"symbol": "C", "root": "C", "quality": "maj", "notes": ["C", "E", "G"], "roman": "I", "func": "tonic"},
            {"symbol": "F", "root": "F", "quality": "maj", "notes": ["F", "A", "C"], "roman": "IV", "func": "predominant"},
            {"symbol": "G7", "root": "G", "quality": "7", "notes": ["G", "B", "D", "F"], "roman": "V7", "func": "dominant"},
            {"symbol": "C", "root": "C", "quality": "maj", "notes": ["C", "E", "G"], "roman": "I", "func": "tonic"},
        ],
        # ii - V - I (Jazz)
        [
            {"symbol": "Dm7", "root": "D", "quality": "m7", "notes": ["D", "F", "A", "C"], "roman": "ii7", "func": "predominant"},
            {"symbol": "G7", "root": "G", "quality": "7", "notes": ["G", "B", "D", "F"], "roman": "V7", "func": "dominant"},
            {"symbol": "Cmaj7", "root": "C", "quality": "maj7", "notes": ["C", "E", "G", "B"], "roman": "Imaj7", "func": "tonic"},
            {"symbol": "Am7", "root": "A", "quality": "m7", "notes": ["A", "C", "E", "G"], "roman": "vi7", "func": "tonic"},
        ],
        # I - vi - IV - V (50s progression)
        [
            {"symbol": "C", "root": "C", "quality": "maj", "notes": ["C", "E", "G"], "roman": "I", "func": "tonic"},
            {"symbol": "Am", "root": "A", "quality": "m", "notes": ["A", "C", "E"], "roman": "vi", "func": "tonic"},
            {"symbol": "F", "root": "F", "quality": "maj", "notes": ["F", "A", "C"], "roman": "IV", "func": "predominant"},
            {"symbol": "G", "root": "G", "quality": "maj", "notes": ["G", "B", "D"], "roman": "V", "func": "dominant"},
        ],
    ]

    measures = []
    num_measures = 16

    import random
    random.seed(hash(file_id))  # Consistent results for same file

    for i in range(num_measures):
        prog = progressions[i // 4 % len(progressions)]
        chord_data = prog[i % 4]

        measure_x = (i % 4) * 0.22 + 0.06
        measure_y = (i // 4) * 0.18 + 0.15

        confidence = 0.85 + random.random() * 0.15

        chord = {
            "id": f"chord-{i}",
            "symbol": chord_data["symbol"],
            "root": chord_data["root"],
            "quality": chord_data["quality"],
            "notes": chord_data["notes"],
            "boundingBox": {
                "x": measure_x + 0.02,
                "y": measure_y + 0.02,
                "width": 0.16,
                "height": 0.12,
            },
            "romanNumeral": chord_data["roman"],
            "function": chord_data["func"],
            "confidence": confidence,
            "beatPosition": 1,
        }

        measures.append({
            "number": i + 1,
            "boundingBox": {
                "x": measure_x,
                "y": measure_y,
                "width": 0.20,
                "height": 0.16,
            },
            "beats": [{
                "number": 1,
                "notes": [
                    {
                        "pitch": f"{note}4",
                        "duration": "quarter",
                        "boundingBox": {
                            "x": measure_x + 0.02 + idx * 0.04,
                            "y": measure_y + 0.04,
                            "width": 0.03,
                            "height": 0.08,
                        }
                    }
                    for idx, note in enumerate(chord_data["notes"])
                ],
                "chord": chord,
            }],
            "localKey": global_key,
            "chords": [chord],
            "timeSignature": {"numerator": 4, "denominator": 4},
        })

    # Add modulation
    modulation = {
        "measureNumber": 9,
        "fromKey": {"tonic": "C", "mode": "major", "signature": 0},
        "toKey": {"tonic": "G", "mode": "major", "signature": 1},
        "pivotChord": measures[7]["chords"][0] if len(measures) > 7 else None,
        "reasoning": "The G major chord (V in C) becomes I in the new key of G major. This is a common pivot chord modulation to the dominant key.",
        "boundingBox": {
            "x": 0.06,
            "y": 0.51,
            "width": 0.88,
            "height": 0.02,
        },
    }

    return {
        "id": file_id,
        "filename": "sheet_music.pdf",
        "pages": [{
            "pageNumber": 1,
            "measures": measures,
        }],
        "globalKey": global_key,
        "modulations": [modulation],
        "chordProgression": {
            "romanNumerals": [m["chords"][0]["romanNumeral"] for m in measures],
            "commonName": "Mixed progressions (Pop, Classic, Jazz, 50s)",
        },
        "status": "completed",
    }
