"""
Analysis pipeline.

Ties the score-vision pass and the harmony engine together and serialises
the result into the shape the frontend consumes: everything in normalised
page coordinates so overlays line up with the page image exactly.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import cv2
import fitz
import numpy as np

from app.services import harmony as H
from app.services import score_vision as sv

UPLOAD_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads')

FUNCTION_BLURBS = {
    'tonic': 'Home. This is where the music feels settled.',
    'subdominant': 'Moving away from home, building towards tension.',
    'dominant': 'Maximum tension - it wants to resolve back to the tonic.',
    'secondary-dominant': 'A borrowed dominant that briefly makes another chord feel like home.',
    'chromatic': 'Outside the key - a colour chord passing through.',
}


def page_count(pdf_path: str) -> int:
    doc = fitz.open(pdf_path)
    try:
        return len(doc)
    finally:
        doc.close()


def analyze_upload(upload_id: str, pdf_path: str, job=None) -> dict:
    """
    Read every page, then resolve harmony across the whole piece.

    Pages are published as they finish so the first page is usable while
    later pages are still being read.
    """
    from app.services import jobs

    folder = os.path.join(UPLOAD_ROOT, upload_id)
    os.makedirs(folder, exist_ok=True)

    total = page_count(pdf_path)
    if job is not None:
        jobs.update(job, pages_total=total, stage='Reading page 1')

    analyzed = []
    doc = fitz.open(pdf_path)
    try:
        for number in range(1, total + 1):
            if job is not None:
                jobs.update(job, stage=f'Reading page {number} of {total}')

            geometry, image = sv.read_page(doc[number - 1])

            image_name = f'page_{number}.png'
            cv2.imwrite(os.path.join(folder, image_name), image,
                        [cv2.IMWRITE_PNG_COMPRESSION, 6])

            analyzed.append({'page': number, 'geometry': geometry,
                             'image': image_name, 'gray': image})

            if job is not None:
                partial = serialize(upload_id, analyzed, H.analyze(analyzed), partial=True)
                jobs.update(job, pages_done=number, result=partial)
    finally:
        doc.close()

    if job is not None:
        jobs.update(job, stage='Working out the harmony')

    reading = H.analyze(analyzed)
    result = serialize(upload_id, analyzed, reading, partial=False)

    with open(os.path.join(folder, 'analysis.json'), 'w') as handle:
        json.dump(result, handle)
    return result


def ink_ceiling(image, system):
    """
    For each column above a system, the highest row the music reaches.

    Chord labels belong above the staff, but how much room is needed there
    changes across the bar with stems, beams and slurs. Measuring the ink
    column by column lets each label sit just clear of what is under it
    instead of every label being pushed up to clear the tallest beam.
    """
    ceiling = system.top - system.space * 7.0
    floor = system.top - system.space * 1.3
    x1 = max(0, int(system.x_left))
    y1 = max(0, int(ceiling))
    y2 = max(y1 + 1, int(floor))

    if image is None:
        return x1, np.full(1, floor)

    band = image[y1:y2, x1:min(image.shape[1], int(system.x_right) + 1)]
    if band.size == 0:
        return x1, np.full(1, floor)

    dark = band < 170
    tops = np.where(dark.any(axis=0), y1 + dark.argmax(axis=0), float(y2))
    return x1, tops.astype(float)


def label_lanes(image, systems: list) -> dict:
    """
    One baseline per system for the chord symbols.

    Chord symbols are engraved on a single line above each system, so they
    all clear the tallest thing in that system rather than each sitting at
    its own height, which would read as ragged. The lane is still kept out
    of the system above it.
    """
    lanes = {}
    previous_bottom = 0.0
    for system in sorted(systems, key=lambda s: s.top):
        _, tops = ink_ceiling(image, system)
        lane = float(tops.min()) if tops.size else system.top - system.space * 3.0
        lane = max(lane, previous_bottom + system.space * 0.4)
        lanes[system.index] = min(lane, system.top - system.space * 1.3)
        previous_bottom = system.bottom
    return lanes


def serialize(upload_id: str, analyzed: list, reading: dict, partial: bool) -> dict:
    key = reading['key']
    keys = reading.get('keys') or [key]
    spans_by_page = {}
    for page_number, span in reading['spans']:
        spans_by_page.setdefault(page_number, []).append(span)

    pages = []
    timeline = []
    measure_offset = 0
    for entry in analyzed:
        geometry = entry['geometry']
        number = entry['page']
        width, height = float(geometry.width), float(geometry.height)

        note_ids = {}
        notes = []
        for index, note in enumerate(geometry.noteheads):
            note_id = f'p{number}n{index}'
            note_ids[id(note)] = note_id
            notes.append({
                'id': note_id,
                'x': note.x1 / width,
                'y': note.y1 / height,
                'width': (note.x2 - note.x1) / width,
                'height': (note.y2 - note.y1) / height,
                'midi': note.midi,
                'name': note.name,
                'filled': note.filled,
                'measure': note.measure_index,
                'system': note.system_index,
            })

        # Measure numbers run continuously across pages so navigation and the
        # ribbon match how a player counts the piece.
        measures = [{
            'index': m.index,
            'number': measure_offset + m.index + 1,
            'system': m.system_index,
            'x': m.x1 / width,
            'y': m.top / height,
            'width': (m.x2 - m.x1) / width,
            'height': (m.bottom - m.top) / height,
        } for m in geometry.measures]

        image = entry.get('gray')
        lanes = label_lanes(image, geometry.systems)
        systems = [{
            'index': s.index,
            'x': s.x_left / width,
            'y': s.top / height,
            'width': (s.x_right - s.x_left) / width,
            'height': (s.bottom - s.top) / height,
            'clef': s.staves[0].clef if s.staves else 'treble',
            'staffSpace': s.space / height,
            'labelLane': lanes[s.index] / height,
        } for s in geometry.systems]

        # How far the music actually reaches above and below each staff, so a
        # chord band covers its notes instead of a guessed fixed margin.
        extents = {}
        for system in geometry.systems:
            pad = system.space * 1.1
            members = [n for n in geometry.noteheads if n.system_index == system.index]
            top = min([n.y1 for n in members], default=system.top) - pad
            bottom = max([n.y2 for n in members], default=system.bottom) + pad
            extents[system.index] = (min(top, system.top - pad),
                                     max(bottom, system.bottom + pad))

        chords = []
        for index, span in enumerate(spans_by_page.get(number, [])):
            top, bottom = extents.get(span.system_index, (0.0, height))
            local_key = keys[span.key_index] if 0 <= span.key_index < len(keys) else key
            sharps_pref = local_key.prefers_sharps

            chord_id = f'p{number}c{index}'
            member_ids = [note_ids[nid] for nid in span.note_ids if nid in note_ids]
            chord = {
                'id': chord_id,
                'page': number,
                'measure': span.measure_index,
                'system': span.system_index,
                'measureNumber': measure_offset + span.measure_index + 1,
                'symbol': span.symbol,
                'root': H.pitch_name(span.root, sharps_pref),
                'quality': span.quality,
                'roman': span.roman,
                'function': span.function,
                'explanation': FUNCTION_BLURBS.get(span.function, ''),
                'confidence': round(span.confidence, 3),
                'beat': span.beat,
                'beats': span.beats,
                'inversion': span.inversion,
                'bass': span.bass_name,
                'tonicizes': span.tonicizes,
                'key': local_key.name,
                'pitchClasses': [H.pitch_name(pc, sharps_pref)
                                 for pc in span.pitch_classes],
                'notes': member_ids,
                'box': {
                    'x': span.x1 / width,
                    'y': top / height,
                    'width': (span.x2 - span.x1) / width,
                    'height': (bottom - top) / height,
                },
            }
            chords.append(chord)
            timeline.append({
                'id': chord_id,
                'page': number,
                'measure': span.measure_index,
                'measureNumber': measure_offset + span.measure_index + 1,
                'symbol': span.symbol,
                'roman': span.roman,
                'function': span.function,
                'confidence': round(span.confidence, 3),
                'beat': span.beat,
                'beats': span.beats,
            })

        pages.append({
            'page': number,
            'width': geometry.width,
            'height': geometry.height,
            'image': f'/uploads/{upload_id}/{entry["image"]}',
            'systems': systems,
            'measures': measures,
            'notes': notes,
            'chords': chords,
        })
        measure_offset += len(geometry.measures)

    sharps = None
    if analyzed:
        first = analyzed[0]['geometry']
        if first.systems and first.systems[0].staves:
            sharps = first.systems[0].staves[0].key_sharps

    # Cadences arrive keyed by position in the chord sequence; give them the
    # chord id and running measure number the frontend works in.
    cadences = []
    for cadence in reading['cadences']:
        position = cadence['index']
        if not (0 <= position < len(timeline)):
            continue
        entry = timeline[position]
        cadences.append({
            'chordId': entry['id'],
            'label': cadence['label'],
            'progression': cadence['progression'],
            'measureNumber': entry['measureNumber'],
        })

    time_signature = reading.get('time_signature')
    sources = {entry['geometry'].source for entry in analyzed}

    return {
        'id': upload_id,
        'partial': partial,
        'key': {
            'name': key.name,
            'tonic': H.pitch_name(key.tonic, key.prefers_sharps),
            'mode': key.mode,
            'confidence': round(key.confidence, 3),
            'sharps': sharps,
            'scale': [H.pitch_name(pc, key.prefers_sharps) for pc in key.scale()],
        },
        'keys': [{
            'name': item.name,
            'tonic': H.pitch_name(item.tonic, item.prefers_sharps),
            'mode': item.mode,
            'confidence': round(item.confidence, 3),
            'scale': [H.pitch_name(pc, item.prefers_sharps) for pc in item.scale()],
        } for item in keys],
        'meter': {
            'numerator': time_signature[0] if time_signature else None,
            'denominator': time_signature[1] if time_signature else None,
            'beatsPerMeasure': reading.get('beats_per_measure', 4.0),
        },
        'source': 'engraved' if sources == {'engraved'} else (
            'mixed' if 'engraved' in sources else 'scanned'),
        'pages': pages,
        'timeline': timeline,
        'cadences': cadences,
        'stats': {
            'measures': sum(len(p['measures']) for p in pages),
            'notes': sum(len(p['notes']) for p in pages),
            'chords': len(timeline),
        },
    }


def cached_result_path(upload_id: str) -> str:
    return os.path.join(UPLOAD_ROOT, upload_id, 'analysis.json')


def load_cached(upload_id: str) -> Optional[dict]:
    path = cached_result_path(upload_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
