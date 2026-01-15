"""
Optical Music Recognition (OMR) service using oemer.

Processes sheet music images to extract musical notation,
then performs harmonic analysis on the results.
"""

import os
import subprocess
import tempfile
import asyncio
from typing import Optional
import json

# Try to import OMR and music analysis libraries
try:
    from music21 import converter, stream, chord, key, roman, note, meter
    HAS_MUSIC21 = True
except ImportError:
    HAS_MUSIC21 = False

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


async def run_omr(image_path: str, output_dir: str) -> Optional[str]:
    """
    Run oemer OMR on an image file.

    Args:
        image_path: Path to the sheet music image
        output_dir: Directory to save the MusicXML output

    Returns:
        Path to the generated MusicXML file, or None if failed
    """
    def _run_oemer():
        try:
            # Run oemer CLI
            result = subprocess.run(
                ["oemer", image_path, "-o", output_dir],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                print(f"oemer error: {result.stderr}")
                return None

            # Find the output MusicXML file
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            musicxml_path = os.path.join(output_dir, f"{base_name}.musicxml")

            if os.path.exists(musicxml_path):
                return musicxml_path

            # Try alternative extensions
            for ext in ['.xml', '.mxl']:
                alt_path = os.path.join(output_dir, f"{base_name}{ext}")
                if os.path.exists(alt_path):
                    return alt_path

            # Check if any musicxml was created
            for f in os.listdir(output_dir):
                if f.endswith(('.musicxml', '.xml', '.mxl')):
                    return os.path.join(output_dir, f)

            return None

        except subprocess.TimeoutExpired:
            print("oemer timed out")
            return None
        except Exception as e:
            print(f"oemer exception: {e}")
            return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_oemer)


def parse_musicxml(musicxml_path: str) -> dict:
    """
    Parse MusicXML file using music21 and extract musical information.

    Returns dict with:
        - key_signature: detected key
        - time_signature: time signature
        - measures: list of measure data with notes and chords
        - notes_by_position: notes with their spatial positions (if available)
    """
    if not HAS_MUSIC21:
        return {"error": "music21 not available"}

    try:
        score = converter.parse(musicxml_path)

        # Detect key signature
        detected_key = score.analyze('key')
        key_info = {
            "tonic": detected_key.tonic.name if detected_key.tonic else "C",
            "mode": detected_key.mode if detected_key.mode else "major",
            "signature": get_key_signature_count(detected_key)
        }

        # Get time signature
        time_sigs = score.recurse().getElementsByClass(meter.TimeSignature)
        time_sig = time_sigs[0] if time_sigs else None
        time_info = {
            "numerator": time_sig.numerator if time_sig else 4,
            "denominator": time_sig.denominator if time_sig else 4
        }

        # Extract measures with notes and chords
        measures_data = []

        for part in score.parts:
            for measure_idx, measure in enumerate(part.getElementsByClass(stream.Measure)):
                measure_num = measure.number if measure.number else measure_idx + 1

                # Get notes in this measure
                notes_in_measure = []
                for element in measure.recurse().notesAndRests:
                    if isinstance(element, note.Note):
                        notes_in_measure.append({
                            "pitch": element.nameWithOctave,
                            "duration": element.duration.type,
                            "offset": float(element.offset),
                            "midi": element.pitch.midi
                        })
                    elif isinstance(element, chord.Chord):
                        notes_in_measure.append({
                            "pitches": [p.nameWithOctave for p in element.pitches],
                            "duration": element.duration.type,
                            "offset": float(element.offset),
                            "is_chord": True
                        })

                # Analyze chords in the measure
                chords_in_measure = analyze_measure_harmony(measure, detected_key)

                measures_data.append({
                    "number": measure_num,
                    "notes": notes_in_measure,
                    "chords": chords_in_measure,
                    "localKey": key_info
                })

        return {
            "globalKey": key_info,
            "timeSignature": time_info,
            "measures": measures_data,
            "totalMeasures": len(measures_data)
        }

    except Exception as e:
        print(f"Error parsing MusicXML: {e}")
        return {"error": str(e)}


def analyze_measure_harmony(measure: stream.Measure, current_key: key.Key) -> list:
    """
    Analyze the harmony in a measure, detecting chords and their functions.
    """
    chords_found = []

    try:
        # Use music21's chord reduction
        chordified = measure.chordify()

        for element in chordified.recurse().getElementsByClass(chord.Chord):
            if len(element.pitches) >= 2:  # At least 2 notes for a chord
                # Get chord symbol
                chord_symbol = element.pitchedCommonName or element.commonName

                # Get Roman numeral analysis
                try:
                    rn = roman.romanNumeralFromChord(element, current_key)
                    roman_numeral = rn.romanNumeral
                    chord_function = get_chord_function(roman_numeral)
                except:
                    roman_numeral = "?"
                    chord_function = "unknown"

                chords_found.append({
                    "symbol": simplify_chord_name(element),
                    "root": element.root().name if element.root() else "?",
                    "quality": element.quality,
                    "notes": [p.name for p in element.pitches],
                    "romanNumeral": roman_numeral,
                    "function": chord_function,
                    "offset": float(element.offset),
                    "confidence": 0.9  # From OMR, generally high confidence
                })
    except Exception as e:
        print(f"Error analyzing measure harmony: {e}")

    return chords_found


def simplify_chord_name(c: chord.Chord) -> str:
    """
    Create a simplified chord symbol from a music21 chord.
    """
    if not c.root():
        return "?"

    root = c.root().name
    quality = c.quality

    if quality == "major":
        return root
    elif quality == "minor":
        return f"{root}m"
    elif quality == "diminished":
        return f"{root}dim"
    elif quality == "augmented":
        return f"{root}aug"
    elif quality == "dominant-seventh":
        return f"{root}7"
    elif quality == "major-seventh":
        return f"{root}maj7"
    elif quality == "minor-seventh":
        return f"{root}m7"
    elif quality == "half-diminished-seventh":
        return f"{root}m7b5"
    elif quality == "diminished-seventh":
        return f"{root}dim7"
    else:
        return f"{root}{quality}" if quality else root


def get_chord_function(roman_numeral: str) -> str:
    """Determine harmonic function from Roman numeral."""
    base = roman_numeral.upper().replace('7', '').replace('MAJ', '').replace('DIM', '').replace('AUG', '')
    base = base.replace('#', '').replace('B', '').replace('+', '').replace('°', '')

    tonic_degrees = ['I', 'III', 'VI']
    predominant_degrees = ['II', 'IV']
    dominant_degrees = ['V', 'VII']

    if base in tonic_degrees:
        return 'tonic'
    elif base in predominant_degrees:
        return 'predominant'
    elif base in dominant_degrees:
        return 'dominant'
    elif '/' in roman_numeral:
        return 'secondary_dominant'
    else:
        return 'unknown'


def get_key_signature_count(k: key.Key) -> int:
    """Get number of sharps (+) or flats (-) in key signature."""
    if not k:
        return 0

    sharps_order = ['F#', 'C#', 'G#', 'D#', 'A#', 'E#', 'B#']
    flats_order = ['Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb', 'Fb']

    key_sharps = {
        'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6, 'C#': 7,
        'e': 1, 'b': 2, 'f#': 3, 'c#': 4, 'g#': 5, 'd#': 6, 'a#': 7
    }
    key_flats = {
        'F': -1, 'Bb': -2, 'Eb': -3, 'Ab': -4, 'Db': -5, 'Gb': -6, 'Cb': -7,
        'd': -1, 'g': -2, 'c': -3, 'f': -4, 'bb': -5, 'eb': -6, 'ab': -7
    }

    tonic = k.tonic.name if k.tonic else 'C'
    if k.mode == 'minor':
        tonic = tonic.lower()

    if tonic in key_sharps:
        return key_sharps[tonic]
    elif tonic in key_flats:
        return key_flats[tonic]

    return 0


async def detect_measure_positions(image_path: str) -> list:
    """
    Detect measure/barline positions in the image using computer vision.

    Returns list of bounding boxes for each detected measure.
    """
    if not HAS_CV2:
        return []

    def _detect():
        try:
            img = cv2.imread(image_path)
            if img is None:
                return []

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            height, width = gray.shape

            # Detect vertical lines (barlines)
            # Use morphological operations to find vertical lines
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, height // 10))
            vertical_lines = cv2.morphologyEx(255 - gray, cv2.MORPH_OPEN, vertical_kernel)

            # Threshold
            _, thresh = cv2.threshold(vertical_lines, 50, 255, cv2.THRESH_BINARY)

            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Filter for barlines (tall, thin vertical lines)
            barlines = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect_ratio = h / max(w, 1)
                if aspect_ratio > 5 and h > height * 0.1:  # Tall and thin
                    barlines.append(x)

            barlines = sorted(set(barlines))

            # Detect staff lines to get vertical bounds
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (width // 5, 1))
            horizontal_lines = cv2.morphologyEx(255 - gray, cv2.MORPH_OPEN, horizontal_kernel)
            _, h_thresh = cv2.threshold(horizontal_lines, 50, 255, cv2.THRESH_BINARY)
            h_contours, _ = cv2.findContours(h_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Group staff lines into systems
            staff_ys = []
            for cnt in h_contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if w > width * 0.3:  # Long horizontal line
                    staff_ys.append(y)

            staff_ys = sorted(staff_ys)

            # Create measure bounding boxes
            measures = []
            if len(barlines) >= 2:
                # Find staff system bounds
                if staff_ys:
                    # Group staff lines into systems (5 lines per staff)
                    systems = []
                    current_system = [staff_ys[0]]
                    for y in staff_ys[1:]:
                        if y - current_system[-1] < height * 0.1:
                            current_system.append(y)
                        else:
                            systems.append(current_system)
                            current_system = [y]
                    systems.append(current_system)

                    for system in systems:
                        system_top = min(system) - 20
                        system_bottom = max(system) + 20
                        system_height = system_bottom - system_top

                        for i in range(len(barlines) - 1):
                            x1, x2 = barlines[i], barlines[i + 1]
                            if x2 - x1 > width * 0.02:  # Minimum measure width
                                measures.append({
                                    "x": x1 / width,
                                    "y": system_top / height,
                                    "width": (x2 - x1) / width,
                                    "height": system_height / height
                                })
                else:
                    # No staff lines detected, use full height
                    for i in range(len(barlines) - 1):
                        x1, x2 = barlines[i], barlines[i + 1]
                        if x2 - x1 > width * 0.02:
                            measures.append({
                                "x": x1 / width,
                                "y": 0.1,
                                "width": (x2 - x1) / width,
                                "height": 0.8
                            })

            return measures

        except Exception as e:
            print(f"Error detecting measure positions: {e}")
            return []

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _detect)


async def process_page_with_omr(file_id: str, page_num: int) -> dict:
    """
    Process a single page with OMR and return analysis results.
    """
    upload_path = os.path.join(UPLOAD_DIR, file_id)
    image_path = os.path.join(upload_path, f"page_{page_num}.png")

    if not os.path.exists(image_path):
        return {"error": f"Page image not found: {image_path}"}

    # Run OMR to get MusicXML
    musicxml_path = await run_omr(image_path, upload_path)

    # Detect measure positions from image
    measure_positions = await detect_measure_positions(image_path)

    # Parse MusicXML if OMR succeeded
    if musicxml_path and os.path.exists(musicxml_path):
        music_data = parse_musicxml(musicxml_path)

        # Merge position data with music data
        if measure_positions and music_data.get("measures"):
            for i, measure in enumerate(music_data["measures"]):
                if i < len(measure_positions):
                    measure["boundingBox"] = measure_positions[i]
                else:
                    # Estimate position for remaining measures
                    measure["boundingBox"] = {
                        "x": 0.05 + (i % 4) * 0.23,
                        "y": 0.15 + (i // 4) * 0.2,
                        "width": 0.2,
                        "height": 0.15
                    }

        return music_data
    else:
        # OMR failed, return detected positions only
        return {
            "error": "OMR processing failed",
            "measurePositions": measure_positions,
            "fallback": True
        }


async def full_analysis(file_id: str, num_pages: int = 1) -> dict:
    """
    Perform full OMR and music analysis on all pages.
    """
    results = {
        "id": file_id,
        "pages": [],
        "globalKey": None,
        "modulations": [],
        "chordProgression": {"romanNumerals": [], "commonName": None},
        "status": "processing"
    }

    all_roman_numerals = []

    for page_num in range(1, num_pages + 1):
        page_result = await process_page_with_omr(file_id, page_num)

        if "error" not in page_result:
            # Set global key from first page
            if results["globalKey"] is None and page_result.get("globalKey"):
                results["globalKey"] = page_result["globalKey"]

            # Collect chord progression
            for measure in page_result.get("measures", []):
                for chord_data in measure.get("chords", []):
                    all_roman_numerals.append(chord_data.get("romanNumeral", "?"))

            results["pages"].append({
                "pageNumber": page_num,
                "measures": page_result.get("measures", []),
                "timeSignature": page_result.get("timeSignature")
            })
        else:
            results["pages"].append({
                "pageNumber": page_num,
                "error": page_result.get("error"),
                "measurePositions": page_result.get("measurePositions", [])
            })

    # Set chord progression
    results["chordProgression"]["romanNumerals"] = all_roman_numerals

    # Default key if none detected
    if results["globalKey"] is None:
        results["globalKey"] = {"tonic": "C", "mode": "major", "signature": 0}

    results["status"] = "completed"

    return results
