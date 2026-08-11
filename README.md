# Music for Dummies

Upload a PDF score and explore its harmony directly on the notation. The app links every chord to the notes that produced it, explains its Roman numeral and harmonic function, and lays the whole progression out as an interactive timeline.

## How score reading works

The backend chooses the most accurate available path for each PDF page:

1. **Engraved PDFs:** notation exported by MuseScore, Finale, Sibelius, Guitar Pro, LilyPond, and similar software usually contains SMuFL music-font glyphs and vector rules. The app reads those symbols and coordinates directly from the PDF. Noteheads, accidentals, clefs, key signatures, meter changes, and barlines are exact.
2. **Scanned PDFs:** image-only pages fall back to a deterministic OpenCV pipeline that finds staves, systems, noteheads, barlines, clefs, key signatures, and accidentals from the pixels.

Both paths preserve page coordinates, so the frontend overlays the same rendered image that was analyzed. Chord regions and note highlights do not drift with browser size or zoom.

## Harmony analysis

The custom harmony engine:

- groups simultaneous and nearby note onsets;
- tests a vocabulary of triads, sevenths, ninths, suspensions, sixths, and altered dominants;
- detects the key with pitch profiles constrained by the written key signature;
- respects written meter changes when choosing harmonic rhythm;
- smooths the progression with tonal voice-leading preferences;
- labels Roman numerals, inversions, harmonic functions, secondary dominants, and cadences;
- reports confidence and keeps passing notes separate from chord tones.

Analysis runs once in a background worker after upload. The frontend polls a read-only status endpoint and receives partial page results while the remaining pages are processed.

## Interface

- **Score view:** function-colored chord regions anchored to the notation.
- **Chord labels:** placed in a measured lane above each system to clear beams and stems.
- **Inspector:** chord quality, inversion, confidence, source notes, chord tones, function, tonicization, cadence, and next chord.
- **Harmonic map:** a scrollable whole-piece timeline grouped by measure and weighted by beat duration.
- **Source badge:** distinguishes exact engraved-PDF reading from scan recognition.

## Stack

- Frontend: React, TypeScript, Vite
- Backend: FastAPI, PyMuPDF, OpenCV, NumPy
- No neural OMR runtime, MusicXML conversion, `music21`, or external analysis service is required.

## Run locally

Prerequisites:

- Node.js 18 or newer
- Python 3.10 or newer

Install and start the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

In another terminal, install and start the frontend:

```bash
cd frontend
npm install
npm run dev -- --port 3000
```

Open [http://localhost:3000](http://localhost:3000).

The Vite development server proxies `/api` and `/uploads` to the backend on port 8000.

## Verify the build

```bash
cd frontend
npm run build

cd ../backend
source .venv/bin/activate
python -m unittest discover -s tests -v
python -m compileall -q app tools tests
```

Large scan fixtures are checksum-pinned in `backend/tests/corpus/manifest.json`. Run them by setting `MUSIC_TEST_CORPUS_DIR` to the directory containing those PDFs; see `backend/tests/corpus/README.md`.

The Playwright helpers in `backend/tools/` can inspect a running app:

```bash
cd backend
source .venv/bin/activate
python tools/probe.py "http://localhost:3000/?id=<upload-id>"
python tools/shoot.py "http://localhost:3000/?id=<upload-id>"
```

## API

- `GET /api/health` — service health
- `POST /api/upload` — upload a PDF and start one background analysis job
- `GET /api/analysis/{id}` — read job progress, partial results, or completed results
- `POST /api/analysis/{id}/reanalyze` — explicitly discard the cache and rerun analysis
- `/uploads/{id}/page_{n}.png` — rendered page image used by the overlays

Completed analyses are cached as JSON beside the uploaded PDF and survive server restarts.

## Current limits

Direct vector reading depends on recognizable SMuFL-compatible music fonts. Other engraved formats and image-only files use the scan pipeline, whose confidence reflects the weaker source. The current CV fallback is aimed at conventional single-staff and grand-staff notation; dense orchestral scores, handwritten music, unusual clefs, and percussion notation need additional work.
