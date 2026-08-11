import type { Cadence, Chord, KeyInfo, Meter, Page } from '../types';
import { FUNCTION_LABELS, alpha, colorFor, confidenceTier } from '../theme';

interface Props {
  chord: Chord | null;
  next: Chord | null;
  cadence: Cadence | null;
  pages: Page[];
  keyInfo?: KeyInfo;
  meter?: Meter;
}

const TIER_TEXT = {
  high: 'Confident reading',
  medium: 'Reasonably sure',
  low: 'Uncertain - check this one',
} as const;

/**
 * Explains one chord in plain language: what it is, what it is doing in the
 * key, which notes on the page produced it, and where it is heading next.
 */
export function ChordInspector({ chord, next, cadence, pages, keyInfo, meter }: Props) {
  if (!chord) {
    return (
      <aside className="inspector inspector-empty">
        <h2>Pick a chord</h2>
        <p>
          Hover or click any coloured region on the score, or any block in the harmonic map,
          to see what it is and why.
        </p>
        {keyInfo && (
          <div className="key-card">
            <span className="key-label">Key</span>
            <strong>{keyInfo.name}</strong>
            <div className="scale-row">
              {keyInfo.scale.map((note, index) => (
                <span key={note} className="scale-note">
                  <em>{index + 1}</em>
                  {note}
                </span>
              ))}
            </div>
          </div>
        )}
      </aside>
    );
  }

  const color = colorFor(chord.function);
  const tier = confidenceTier(chord.confidence);
  const page = pages.find((p) => p.page === chord.page);
  const member = new Set(chord.notes);
  const byName = new Map<string, { name: string; midi: number }>();
  (page?.notes ?? [])
    .filter((note) => member.has(note.id))
    .forEach((note) => {
      if (!byName.has(note.name)) byName.set(note.name, note);
    });
  const sorted = [...byName.values()].sort((a, b) => a.midi - b.midi);
  const chordTones = new Set(chord.pitchClasses);
  const isChordTone = (name: string) => chordTones.has(name.replace(/-?\d+$/, ''));

  return (
    <aside className="inspector">
      <div className="inspector-head" style={{ borderColor: alpha(color, 0.6) }}>
        <div className="inspector-symbol" style={{ color }}>
          {chord.symbol}
        </div>
        <div className="inspector-roman">
          <span style={{ background: alpha(color, 0.18), color }}>{chord.roman}</span>
          <small>
            bar {chord.measureNumber ?? chord.measure + 1}
            {meter?.numerator ? `, beat ${chord.beat + 1}` : ''}
          </small>
        </div>
      </div>

      {cadence && (
        <div className="cadence-banner">
          <strong>{cadence.label}</strong>
          {cadence.progression && <span>{cadence.progression}</span>}
          <p>The phrase comes to rest here.</p>
        </div>
      )}

      <dl className="inspector-facts">
        <div>
          <dt>Function</dt>
          <dd style={{ color }}>{FUNCTION_LABELS[chord.function]}</dd>
        </div>
        {(chord.key || keyInfo?.name) && (
          <div>
            <dt>Key</dt>
            <dd>{chord.key ?? keyInfo?.name}</dd>
          </div>
        )}
        <div>
          <dt>Quality</dt>
          <dd>{chord.quality}</dd>
        </div>
        {chord.inversion > 0 && chord.bass && (
          <div>
            <dt>Inversion</dt>
            <dd>
              {chord.inversion === 1 ? 'first' : chord.inversion === 2 ? 'second' : 'third'} — {chord.bass} in the bass
            </dd>
          </div>
        )}
        <div>
          <dt>Reading</dt>
          <dd className={`tier-text tier-${tier}`}>
            {TIER_TEXT[tier]} ({Math.round(chord.confidence * 100)}%)
          </dd>
        </div>
      </dl>

      <p className="inspector-blurb">{chord.explanation}</p>

      {chord.tonicizes && (
        <p className="inspector-blurb accent">
          It is acting as the dominant of <strong>{chord.tonicizes}</strong>, borrowing tension
          from another key for a moment.
        </p>
      )}

      <div className="inspector-section">
        <h3>Notes written here</h3>
        <div className="note-pills">
          {sorted.map((note) => {
            const belongs = isChordTone(note.name);
            return (
              <span
                key={note.name}
                className={`note-pill ${belongs ? '' : 'passing'}`}
                style={{ borderColor: belongs ? alpha(color, 0.6) : undefined }}
                title={belongs ? 'Part of the chord' : 'Passing or decorative note'}
              >
                {note.name}
              </span>
            );
          })}
          {!sorted.length && <span className="muted">No notes linked</span>}
        </div>
        <p className="pill-legend">
          Outlined notes belong to the chord; faded ones are passing or decorative.
        </p>
      </div>

      <div className="inspector-section">
        <h3>Chord tones</h3>
        <div className="note-pills">
          {chord.pitchClasses.map((pc) => (
            <span key={pc} className="note-pill solid" style={{ background: alpha(color, 0.25) }}>
              {pc}
            </span>
          ))}
        </div>
      </div>

      {next && (
        <div className="inspector-section next-up">
          <h3>Goes to</h3>
          <div className="next-chord">
            <span style={{ color: colorFor(next.function) }}>{next.symbol}</span>
            <small>{next.roman}</small>
          </div>
          <p className="muted">
            {chord.function === 'dominant' && next.function === 'tonic'
              ? 'Tension resolving home — the strongest move in tonal music.'
              : chord.function === 'secondary-dominant'
                ? 'A borrowed dominant pulling towards its target.'
                : 'The harmony keeps moving.'}
          </p>
        </div>
      )}
    </aside>
  );
}
