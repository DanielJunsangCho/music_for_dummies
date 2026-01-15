import type { AnalysisResult, ChordAnalysis, Key, Measure, Modulation, PageAnalysis } from '../types/music';

// Generate realistic mock analysis data based on common chord progressions
export function generateMockAnalysis(filename: string): AnalysisResult {
  const globalKey: Key = { tonic: 'C', mode: 'major', signature: 0 };

  // Common chord progressions for demonstration
  const chordProgressions = [
    // I - V - vi - IV (Pop progression)
    [
      { symbol: 'C', root: 'C', quality: 'maj', notes: ['C', 'E', 'G'], roman: 'I', func: 'tonic' as const },
      { symbol: 'G', root: 'G', quality: 'maj', notes: ['G', 'B', 'D'], roman: 'V', func: 'dominant' as const },
      { symbol: 'Am', root: 'A', quality: 'm', notes: ['A', 'C', 'E'], roman: 'vi', func: 'tonic' as const },
      { symbol: 'F', root: 'F', quality: 'maj', notes: ['F', 'A', 'C'], roman: 'IV', func: 'predominant' as const },
    ],
    // I - IV - V - I (Classic)
    [
      { symbol: 'C', root: 'C', quality: 'maj', notes: ['C', 'E', 'G'], roman: 'I', func: 'tonic' as const },
      { symbol: 'F', root: 'F', quality: 'maj', notes: ['F', 'A', 'C'], roman: 'IV', func: 'predominant' as const },
      { symbol: 'G7', root: 'G', quality: '7', notes: ['G', 'B', 'D', 'F'], roman: 'V7', func: 'dominant' as const },
      { symbol: 'C', root: 'C', quality: 'maj', notes: ['C', 'E', 'G'], roman: 'I', func: 'tonic' as const },
    ],
    // ii - V - I (Jazz)
    [
      { symbol: 'Dm7', root: 'D', quality: 'm7', notes: ['D', 'F', 'A', 'C'], roman: 'ii7', func: 'predominant' as const },
      { symbol: 'G7', root: 'G', quality: '7', notes: ['G', 'B', 'D', 'F'], roman: 'V7', func: 'dominant' as const },
      { symbol: 'Cmaj7', root: 'C', quality: 'maj7', notes: ['C', 'E', 'G', 'B'], roman: 'Imaj7', func: 'tonic' as const },
      { symbol: 'Am7', root: 'A', quality: 'm7', notes: ['A', 'C', 'E', 'G'], roman: 'vi7', func: 'tonic' as const },
    ],
    // I - vi - IV - V (50s progression)
    [
      { symbol: 'C', root: 'C', quality: 'maj', notes: ['C', 'E', 'G'], roman: 'I', func: 'tonic' as const },
      { symbol: 'Am', root: 'A', quality: 'm', notes: ['A', 'C', 'E'], roman: 'vi', func: 'tonic' as const },
      { symbol: 'F', root: 'F', quality: 'maj', notes: ['F', 'A', 'C'], roman: 'IV', func: 'predominant' as const },
      { symbol: 'G', root: 'G', quality: 'maj', notes: ['G', 'B', 'D'], roman: 'V', func: 'dominant' as const },
    ],
  ];

  // Generate measures with chord analysis
  const measures: Measure[] = [];
  const numMeasures = 16;

  for (let i = 0; i < numMeasures; i++) {
    const progression = chordProgressions[Math.floor(i / 4) % chordProgressions.length];
    const chordData = progression[i % 4];

    const measureX = (i % 4) * 0.22 + 0.06;
    const measureY = Math.floor(i / 4) * 0.18 + 0.15;

    const chord: ChordAnalysis = {
      id: `chord-${i}`,
      symbol: chordData.symbol,
      root: chordData.root,
      quality: chordData.quality,
      notes: chordData.notes,
      boundingBox: {
        x: measureX + 0.02,
        y: measureY + 0.02,
        width: 0.16,
        height: 0.12,
      },
      romanNumeral: chordData.roman,
      function: chordData.func,
      confidence: 0.85 + Math.random() * 0.15,
      beatPosition: 1,
    };

    measures.push({
      number: i + 1,
      boundingBox: {
        x: measureX,
        y: measureY,
        width: 0.20,
        height: 0.16,
      },
      beats: [
        {
          number: 1,
          notes: chordData.notes.map((note, idx) => ({
            pitch: `${note}4`,
            duration: 'quarter',
            boundingBox: {
              x: measureX + 0.02 + idx * 0.04,
              y: measureY + 0.04,
              width: 0.03,
              height: 0.08,
            },
          })),
          chord,
        },
      ],
      localKey: globalKey,
      chords: [chord],
      timeSignature: { numerator: 4, denominator: 4 },
    });
  }

  // Add a modulation for demonstration (measure 9 - modulate to G major)
  const modulation: Modulation = {
    measureNumber: 9,
    fromKey: { tonic: 'C', mode: 'major', signature: 0 },
    toKey: { tonic: 'G', mode: 'major', signature: 1 },
    pivotChord: measures[7].chords[0],
    reasoning: 'The G major chord (V in C) becomes I in the new key of G major. This is a common pivot chord modulation to the dominant key.',
    boundingBox: {
      x: 0.06,
      y: 0.51,
      width: 0.88,
      height: 0.02,
    },
  };

  const page: PageAnalysis = {
    pageNumber: 1,
    measures,
  };

  return {
    id: `analysis-${Date.now()}`,
    filename,
    pages: [page],
    globalKey,
    modulations: [modulation],
    chordProgression: {
      romanNumerals: ['I', 'V', 'vi', 'IV', 'I', 'IV', 'V7', 'I', 'ii7', 'V7', 'Imaj7', 'vi7', 'I', 'vi', 'IV', 'V'],
      commonName: 'Mixed progressions (Pop, Classic, Jazz, 50s)',
    },
    status: 'completed',
  };
}

// Helper to get chord function color
export function getChordFunctionColor(func: string): string {
  const colors: Record<string, string> = {
    tonic: 'var(--accent-tonic)',
    predominant: 'var(--accent-predominant)',
    dominant: 'var(--accent-dominant)',
    secondary_dominant: '#fb923c',
    borrowed: 'var(--accent-borrowed)',
    diminished: '#94a3b8',
    augmented: '#fbbf24',
    passing: '#6b7280',
    neighbor: '#6b7280',
    unknown: '#6b7280',
  };
  return colors[func] || colors.unknown;
}

// Helper to get chord function description
export function getChordFunctionDescription(func: string): string {
  const descriptions: Record<string, string> = {
    tonic: 'Creates stability and rest. The "home" of the key.',
    predominant: 'Creates tension that leads to the dominant. Often includes IV and ii chords.',
    dominant: 'Creates strong tension that wants to resolve to tonic. Usually V or V7.',
    secondary_dominant: 'A dominant chord borrowed from another key to tonicize a non-tonic chord.',
    borrowed: 'A chord borrowed from the parallel major or minor key.',
    diminished: 'An unstable chord often used as a passing or leading tone chord.',
    augmented: 'An unstable chord with raised 5th, often used chromatically.',
    passing: 'A chord used to connect two other chords smoothly.',
    neighbor: 'A chord that decorates another chord by moving away and back.',
    unknown: 'Chord function could not be determined.',
  };
  return descriptions[func] || descriptions.unknown;
}
