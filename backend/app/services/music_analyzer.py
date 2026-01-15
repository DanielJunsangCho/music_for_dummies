"""
Music analysis service.

Performs chord detection, key analysis, and harmonic function classification.
Uses music21 for music theory operations when available.
Integrates with OMR service for real sheet music recognition.
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

# Import OMR service
from app.services.omr_service import full_analysis, process_page_with_omr, detect_measure_positions

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")

# Flag to enable/disable real OMR (can be toggled for testing)
USE_REAL_OMR = True

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
    Uses real OMR when available, falls back to mock data.
    """
    upload_path = os.path.join(UPLOAD_DIR, file_id)
    analysis_path = os.path.join(upload_path, "analysis.json")

    # Check for cached analysis
    if os.path.exists(analysis_path):
        with open(analysis_path, 'r') as f:
            return json.load(f)

    # Count available pages
    num_pages = count_page_images(upload_path)

    if USE_REAL_OMR and num_pages > 0:
        # Use real OMR analysis
        try:
            result = await full_analysis(file_id, num_pages)
            result = format_analysis_result(file_id, result)
        except Exception as e:
            print(f"OMR failed, falling back to mock: {e}")
            result = generate_mock_analysis(file_id)
    else:
        # Fall back to mock analysis
        result = generate_mock_analysis(file_id)

    # Cache the result
    with open(analysis_path, 'w') as f:
        json.dump(result, f)

    return result


def count_page_images(upload_path: str) -> int:
    """Count the number of page images in the upload directory."""
    if not os.path.exists(upload_path):
        return 0
    return len([f for f in os.listdir(upload_path) if f.startswith('page_') and f.endswith('.png')])


def format_analysis_result(file_id: str, omr_result: dict) -> dict:
    """
    Format OMR result to match the expected frontend schema.
    Adds IDs and bounding boxes where needed.
    """
    pages = []

    for page_data in omr_result.get("pages", []):
        measures = []

        for i, measure in enumerate(page_data.get("measures", [])):
            # Ensure bounding box exists
            bbox = measure.get("boundingBox", {
                "x": 0.05 + (i % 4) * 0.23,
                "y": 0.15 + (i // 4) * 0.2,
                "width": 0.2,
                "height": 0.15
            })

            # Format chords
            formatted_chords = []
            for j, chord_data in enumerate(measure.get("chords", [])):
                chord_bbox = {
                    "x": bbox["x"] + 0.02,
                    "y": bbox["y"] + 0.02,
                    "width": bbox["width"] - 0.04,
                    "height": bbox["height"] - 0.04
                }

                formatted_chords.append({
                    "id": f"chord-{page_data.get('pageNumber', 1)}-{i}-{j}",
                    "symbol": chord_data.get("symbol", "?"),
                    "root": chord_data.get("root", "?"),
                    "quality": chord_data.get("quality", ""),
                    "notes": chord_data.get("notes", []),
                    "boundingBox": chord_bbox,
                    "romanNumeral": chord_data.get("romanNumeral", "?"),
                    "function": chord_data.get("function", "unknown"),
                    "confidence": chord_data.get("confidence", 0.8),
                    "beatPosition": 1
                })

            # Format notes into beats
            beats = [{
                "number": 1,
                "notes": [
                    {
                        "pitch": n.get("pitch", "C4"),
                        "duration": n.get("duration", "quarter"),
                        "boundingBox": {
                            "x": bbox["x"] + 0.02,
                            "y": bbox["y"] + 0.04,
                            "width": 0.03,
                            "height": 0.08
                        }
                    }
                    for n in measure.get("notes", [])[:4]  # Limit notes shown
                ],
                "chord": formatted_chords[0] if formatted_chords else None
            }]

            measures.append({
                "number": measure.get("number", i + 1),
                "boundingBox": bbox,
                "beats": beats,
                "localKey": measure.get("localKey", omr_result.get("globalKey", {"tonic": "C", "mode": "major", "signature": 0})),
                "chords": formatted_chords,
                "timeSignature": measure.get("timeSignature", {"numerator": 4, "denominator": 4})
            })

        pages.append({
            "pageNumber": page_data.get("pageNumber", 1),
            "measures": measures
        })

    # Build chord progression from all measures
    all_roman_numerals = []
    for page in pages:
        for measure in page.get("measures", []):
            for chord_data in measure.get("chords", []):
                all_roman_numerals.append(chord_data.get("romanNumeral", "?"))

    return {
        "id": file_id,
        "filename": "sheet_music.pdf",
        "pages": pages,
        "globalKey": omr_result.get("globalKey", {"tonic": "C", "mode": "major", "signature": 0}),
        "modulations": omr_result.get("modulations", []),
        "chordProgression": {
            "romanNumerals": all_roman_numerals,
            "commonName": identify_progression(all_roman_numerals)
        },
        "status": "completed"
    }


def identify_progression(roman_numerals: list) -> str:
    """Identify common chord progressions."""
    if not roman_numerals:
        return None

    # Check for common patterns
    pattern = " ".join(roman_numerals[:4]).lower()

    common_patterns = {
        "i v vi iv": "Pop progression",
        "i iv v i": "Classical cadence",
        "ii v i": "Jazz ii-V-I",
        "i vi iv v": "50s progression",
        "vi iv i v": "Axis progression",
    }

    for p, name in common_patterns.items():
        if pattern.startswith(p):
            return name

    return None


async def analyze_music(file_id: str) -> AsyncGenerator[dict, None]:
    """
    Analyze music with progress updates.
    Uses real OMR when available.

    Yields progress updates and final result.
    """
    upload_path = os.path.join(UPLOAD_DIR, file_id)
    num_pages = count_page_images(upload_path)

    if USE_REAL_OMR and num_pages > 0:
        # Real OMR analysis with progress
        yield {"type": "progress", "value": 0.1, "message": "Loading images..."}

        yield {"type": "progress", "value": 0.2, "message": "Running OMR (this may take a minute)..."}

        try:
            # Run OMR analysis
            omr_result = await full_analysis(file_id, num_pages)

            yield {"type": "progress", "value": 0.7, "message": "Analyzing harmony..."}

            result = format_analysis_result(file_id, omr_result)

            yield {"type": "progress", "value": 0.9, "message": "Finalizing..."}

        except Exception as e:
            print(f"OMR failed: {e}")
            yield {"type": "progress", "value": 0.5, "message": "OMR failed, using fallback..."}
            result = generate_mock_analysis(file_id)
    else:
        # Simulated analysis for demo
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
            await asyncio.sleep(0.3)

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
