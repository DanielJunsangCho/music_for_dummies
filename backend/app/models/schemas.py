"""
Pydantic schemas for API request/response models.
These mirror the TypeScript types in the frontend.
"""

from typing import Optional
from pydantic import BaseModel


class BoundingBox(BaseModel):
    """Spatial coordinates as percentages of page dimensions."""
    x: float
    y: float
    width: float
    height: float


class Key(BaseModel):
    """Musical key representation."""
    tonic: str
    mode: str  # 'major' or 'minor'
    signature: int  # Positive for sharps, negative for flats


class NoteInfo(BaseModel):
    """Individual note information."""
    pitch: str
    duration: str
    boundingBox: BoundingBox


class ChordAnalysis(BaseModel):
    """Detailed chord analysis."""
    id: str
    symbol: str
    root: str
    quality: str
    bass: Optional[str] = None
    notes: list[str]
    boundingBox: BoundingBox
    romanNumeral: str
    function: str  # ChordFunction type
    confidence: float
    beatPosition: int


class Beat(BaseModel):
    """Beat within a measure."""
    number: int
    notes: list[NoteInfo]
    chord: Optional[ChordAnalysis] = None


class Measure(BaseModel):
    """Measure analysis."""
    number: int
    boundingBox: BoundingBox
    beats: list[Beat]
    localKey: Key
    chords: list[ChordAnalysis]
    timeSignature: dict  # {numerator, denominator}


class Modulation(BaseModel):
    """Key change detection."""
    measureNumber: int
    fromKey: Key
    toKey: Key
    pivotChord: Optional[ChordAnalysis] = None
    reasoning: str
    boundingBox: BoundingBox


class ChordProgression(BaseModel):
    """Overall chord progression."""
    romanNumerals: list[str]
    commonName: Optional[str] = None


class PageAnalysis(BaseModel):
    """Analysis for a single page."""
    pageNumber: int
    measures: list[Measure]
    imageUrl: Optional[str] = None


class AnalysisResult(BaseModel):
    """Complete analysis result."""
    id: str
    filename: str
    pages: list[PageAnalysis]
    globalKey: Key
    modulations: list[Modulation]
    chordProgression: ChordProgression
    status: str  # 'pending', 'processing', 'completed', 'error'
    error: Optional[str] = None


class UploadResponse(BaseModel):
    """Response from file upload."""
    id: str
    filename: str
    status: str
    message: str


class AnalysisStatus(BaseModel):
    """Status update for analysis progress."""
    id: str
    status: str
    progress: float
    message: Optional[str] = None
