export type HarmonicFunction =
  | 'tonic'
  | 'subdominant'
  | 'dominant'
  | 'secondary-dominant'
  | 'chromatic';

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Note extends Box {
  id: string;
  midi: number;
  name: string;
  filled: boolean;
  measure: number;
  system: number;
}

export interface Measure extends Box {
  index: number;
  number: number;
  system: number;
}

export interface SystemBox extends Box {
  index: number;
  clef: string;
  staffSpace: number;
  /** Where chord symbols sit: measured to clear the tallest ink in the system. */
  labelLane: number;
}

export interface Chord {
  id: string;
  page: number;
  measure: number;
  measureNumber: number;
  system: number;
  symbol: string;
  root: string;
  quality: string;
  roman: string;
  function: HarmonicFunction;
  explanation: string;
  confidence: number;
  beat: number;
  beats: number;
  inversion: number;
  bass: string | null;
  tonicizes: string | null;
  /** Local key used for this chord's Roman numeral (multi-song books). */
  key?: string;
  pitchClasses: string[];
  notes: string[];
  box: Box;
}

export interface Page {
  page: number;
  width: number;
  height: number;
  image: string;
  systems: SystemBox[];
  measures: Measure[];
  notes: Note[];
  chords: Chord[];
}

export interface TimelineEntry {
  id: string;
  page: number;
  measure: number;
  measureNumber: number;
  symbol: string;
  roman: string;
  function: HarmonicFunction;
  confidence: number;
  beat: number;
  beats: number;
}

export interface Cadence {
  chordId: string;
  label: string;
  progression: string | null;
  measureNumber: number;
}

export interface Meter {
  numerator: number | null;
  denominator: number | null;
  beatsPerMeasure: number;
}

export interface KeyInfo {
  name: string;
  tonic: string;
  mode: string;
  confidence: number;
  sharps?: number | null;
  scale: string[];
}

export interface Progress {
  stage: string;
  pagesDone: number;
  pagesTotal: number;
  elapsed: number;
}

export interface Analysis {
  id: string;
  status: 'queued' | 'running' | 'complete' | 'error';
  progress: Progress;
  error?: string;
  partial?: boolean;
  key?: KeyInfo;
  /** Distinct local keys when a book contains more than one song/tonality. */
  keys?: KeyInfo[];
  meter?: Meter;
  /** How the notation was read: from the PDF's own glyphs, or from the pixels. */
  source?: 'engraved' | 'scanned' | 'mixed';
  pages?: Page[];
  timeline?: TimelineEntry[];
  cadences?: Cadence[];
  stats?: { measures: number; notes: number; chords: number };
}
