# Music for Dummies

An educational web application that helps musicians understand music theory directly from PDF sheet music.

## High-Level Architecture

```
+------------------+     +-------------------+     +----------------------+
|                  |     |                   |     |                      |
|   React Frontend |<--->|  FastAPI Backend  |<--->|  Analysis Pipeline   |
|   (TypeScript)   |     |  (Python)         |     |  (OMR + Theory)      |
|                  |     |                   |     |                      |
+------------------+     +-------------------+     +----------------------+
        |                        |                          |
        v                        v                          v
+------------------+     +-------------------+     +----------------------+
| - PDF Viewer     |     | - PDF Processing  |     | - Note Detection     |
| - Interactive    |     | - API Endpoints   |     | - Chord Inference    |
|   Overlays       |     | - WebSocket for   |     | - Key Detection      |
| - Tooltips       |     |   real-time       |     | - Modulation Track   |
| - Sidebar        |     |   updates         |     | - Roman Numeral      |
+------------------+     +-------------------+     +----------------------+
```

## Music Analysis Pipeline

```
PDF Upload
    |
    v
+-------------------+
| PDF to Image      |  (pdf2image / PyMuPDF)
| Conversion        |
+-------------------+
    |
    v
+-------------------+
| Optical Music     |  (Audiveris / oemer / custom CNN)
| Recognition (OMR) |
+-------------------+
    |
    v
+-------------------+
| MusicXML/MEI      |  Structured music notation format
| Output            |
+-------------------+
    |
    v
+-------------------+
| Note Extraction   |  Parse notes, rests, time signatures
| & Grouping        |
+-------------------+
    |
    v
+-------------------+
| Chord Detection   |  Group simultaneous notes into chords
| Algorithm         |
+-------------------+
    |
    v
+-------------------+
| Key Detection     |  Krumhansl-Schmuckler algorithm
| Algorithm         |
+-------------------+
    |
    v
+-------------------+
| Harmonic Analysis |  Roman numerals, function, progressions
+-------------------+
    |
    v
+-------------------+
| Modulation        |  Track key changes via pivot chords
| Detection         |
+-------------------+
    |
    v
+-------------------+
| JSON Output with  |  Bounding boxes + music theory data
| Spatial Mapping   |
+-------------------+
```

## Tech Stack Justification

### Frontend: React + TypeScript
- **Why React**: Component-based architecture ideal for interactive overlays
- **Why TypeScript**: Type safety for complex music theory data structures
- **PDF Rendering**: react-pdf (PDF.js wrapper) for accurate rendering
- **State Management**: Zustand (lightweight, TypeScript-friendly)

### Backend: Python + FastAPI
- **Why Python**: Best ecosystem for music analysis (music21, librosa)
- **Why FastAPI**: Async support, automatic OpenAPI docs, fast performance
- **OMR Options**:
  - Audiveris (Java, most accurate)
  - oemer (Python, neural network-based)
  - Custom fallback for simple scores

### Key Libraries
- **music21**: MIT's comprehensive music theory library
- **pdf2image**: PDF to image conversion
- **Pillow**: Image processing
- **numpy**: Numerical operations for analysis

## Project Structure

```
music_for_dummies/
├── frontend/                 # React TypeScript app
│   ├── src/
│   │   ├── components/       # UI components
│   │   │   ├── PDFViewer/    # PDF rendering
│   │   │   ├── Overlay/      # Interactive overlays
│   │   │   ├── Tooltip/      # Music theory tooltips
│   │   │   └── Sidebar/      # Analysis sidebar
│   │   ├── hooks/            # Custom React hooks
│   │   ├── store/            # Zustand state management
│   │   ├── types/            # TypeScript interfaces
│   │   ├── utils/            # Helper functions
│   │   └── api/              # Backend API calls
│   └── package.json
│
├── backend/                  # Python FastAPI server
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── routers/          # API route handlers
│   │   ├── services/         # Business logic
│   │   │   ├── pdf_processor.py
│   │   │   ├── omr_service.py
│   │   │   └── music_analyzer.py
│   │   ├── models/           # Pydantic models
│   │   └── utils/            # Helper utilities
│   └── requirements.txt
│
├── shared/                   # Shared type definitions
│   └── types.ts
│
└── README.md
```

## Music Theory Data Model

```typescript
interface AnalysisResult {
  pages: PageAnalysis[];
  globalKey: Key;
  modulations: Modulation[];
  chordProgression: ChordProgression;
}

interface PageAnalysis {
  pageNumber: number;
  measures: Measure[];
  imageUrl: string;
}

interface Measure {
  number: number;
  boundingBox: BoundingBox;
  beats: Beat[];
  localKey: Key;
  chords: ChordAnalysis[];
}

interface ChordAnalysis {
  symbol: string;           // "Cmaj7", "Am", "D7/F#"
  notes: string[];          // ["C", "E", "G", "B"]
  boundingBox: BoundingBox;
  romanNumeral: string;     // "I", "vi", "V7"
  function: ChordFunction;  // "tonic", "dominant", etc.
  confidence: number;       // 0-1 confidence score
}

interface Modulation {
  measureNumber: number;
  fromKey: Key;
  toKey: Key;
  pivotChord?: ChordAnalysis;
  reasoning: string;
}
```

## Features

### MVP (Current Implementation)
- [x] PDF upload and full-screen display
- [x] Page-by-page navigation
- [x] Hover overlays for measures/chords
- [x] Chord name and notes display
- [x] Roman numeral analysis
- [x] Key detection
- [x] Mock data for demonstration

### Future Enhancements
- [ ] Real OMR integration (Audiveris/oemer)
- [ ] ML-based chord detection improvement
- [ ] Audio playback of chords
- [ ] MIDI export
- [ ] Annotation saving
- [ ] Chrome extension version
- [ ] DAW plugin (VST/AU)

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.10+
- pip

### Installation

```bash
# Clone repository
git clone https://github.com/juncho/music_for_dummies.git
cd music_for_dummies

# Install frontend dependencies
cd frontend
npm install

# Install backend dependencies
cd ../backend
pip install -r requirements.txt

# Start backend server
uvicorn app.main:app --reload --port 8000

# In another terminal, start frontend
cd frontend
npm run dev
```

## API Endpoints

- `POST /api/upload` - Upload PDF sheet music
- `GET /api/analysis/{id}` - Get analysis results
- `GET /api/page/{id}/{page}` - Get page image and overlays
- `WebSocket /ws/analysis/{id}` - Real-time analysis updates

## TODOs for Improving Accuracy

1. **Better OMR**: Integrate Audiveris for production-grade music recognition
2. **ML Chord Detection**: Train custom model on annotated chord datasets
3. **Voice Leading Analysis**: Track individual voices for better chord identification
4. **Genre-Specific Models**: Jazz vs Classical vs Pop chord vocabularies
5. **User Feedback Loop**: Allow users to correct detected chords
6. **Ensemble Scores**: Support for full orchestral scores

## License

MIT License - See LICENSE file for details
