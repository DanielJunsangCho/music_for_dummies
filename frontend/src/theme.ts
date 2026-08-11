import type { HarmonicFunction } from './types';

/**
 * One colour per harmonic function, used identically on the score, the
 * ribbon and the inspector. The colour is the thing that ties a highlight
 * on the page to its block in the timeline.
 */
export const FUNCTION_COLORS: Record<HarmonicFunction, string> = {
  tonic: '#34d399',
  subdominant: '#fbbf24',
  dominant: '#fb7185',
  'secondary-dominant': '#a78bfa',
  chromatic: '#94a3b8',
};

export const FUNCTION_LABELS: Record<HarmonicFunction, string> = {
  tonic: 'Tonic',
  subdominant: 'Subdominant',
  dominant: 'Dominant',
  'secondary-dominant': 'Secondary dominant',
  chromatic: 'Chromatic',
};

export const FUNCTION_ORDER: HarmonicFunction[] = [
  'tonic',
  'subdominant',
  'dominant',
  'secondary-dominant',
  'chromatic',
];

export function colorFor(fn: HarmonicFunction): string {
  return FUNCTION_COLORS[fn] ?? FUNCTION_COLORS.chromatic;
}

export function alpha(hex: string, value: number): string {
  const clean = hex.replace('#', '');
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${value})`;
}

export type ConfidenceTier = 'high' | 'medium' | 'low';

export function confidenceTier(value: number): ConfidenceTier {
  if (value >= 0.75) return 'high';
  if (value >= 0.5) return 'medium';
  return 'low';
}
