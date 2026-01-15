// Core music theory types for the application

export interface BoundingBox {
  x: number;      // Left position (percentage of page width)
  y: number;      // Top position (percentage of page height)
  width: number;  // Width (percentage of page width)
  height: number; // Height (percentage of page height)
}

export interface Key {
  tonic: string;        // "C", "G", "F#", etc.
  mode: 'major' | 'minor';
  signature: number;    // Number of sharps (+) or flats (-)
}

export type ChordFunction =
  | 'tonic'
  | 'predominant'
  | 'dominant'
  | 'secondary_dominant'
  | 'borrowed'
  | 'diminished'
  | 'augmented'
  | 'passing'
  | 'neighbor'
  | 'unknown';

export interface ChordAnalysis {
  id: string;
  symbol: string;           // "Cmaj7", "Am", "D7/F#"
  root: string;             // "C", "A", "D"
  quality: string;          // "maj7", "m", "7"
  bass?: string;            // For slash chords: "F#"
  notes: string[];          // ["C", "E", "G", "B"]
  boundingBox: BoundingBox;
  romanNumeral: string;     // "I", "vi", "V7/V"
  function: ChordFunction;
  confidence: number;       // 0-1 confidence score
  beatPosition: number;     // Position within measure (1, 2, 3, 4)
}

export interface Beat {
  number: number;
  notes: NoteInfo[];
  chord?: ChordAnalysis;
}

export interface NoteInfo {
  pitch: string;      // "C4", "G#5"
  duration: string;   // "quarter", "half", "whole"
  boundingBox: BoundingBox;
}

export interface Measure {
  number: number;
  boundingBox: BoundingBox;
  beats: Beat[];
  localKey: Key;
  chords: ChordAnalysis[];
  timeSignature: {
    numerator: number;
    denominator: number;
  };
}

export interface Modulation {
  measureNumber: number;
  fromKey: Key;
  toKey: Key;
  pivotChord?: ChordAnalysis;
  reasoning: string;
  boundingBox: BoundingBox;
}

export interface ChordProgression {
  romanNumerals: string[];
  commonName?: string;  // "I-V-vi-IV" => "Pop progression"
}

export interface PageAnalysis {
  pageNumber: number;
  measures: Measure[];
  imageUrl?: string;
}

export interface AnalysisResult {
  id: string;
  filename: string;
  pages: PageAnalysis[];
  globalKey: Key;
  modulations: Modulation[];
  chordProgression: ChordProgression;
  status: 'pending' | 'processing' | 'completed' | 'error';
  error?: string;
}

// UI State types
export interface HoverTarget {
  type: 'chord' | 'measure' | 'note' | 'modulation';
  data: ChordAnalysis | Measure | NoteInfo | Modulation;
  position: { x: number; y: number };
}

export interface TooltipContent {
  title: string;
  subtitle?: string;
  details: { label: string; value: string }[];
  explanation?: string;
}
