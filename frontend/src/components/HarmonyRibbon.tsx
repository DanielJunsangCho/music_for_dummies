import { useMemo } from 'react';
import type { Cadence, Chord, KeyInfo, Page } from '../types';
import { alpha, colorFor, confidenceTier } from '../theme';

interface Props {
  pages: Page[];
  cadences: Cadence[];
  keyInfo?: KeyInfo;
  hovered: string | null;
  selected: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string | null) => void;
}

/**
 * The whole piece as one horizontal strip of harmony.
 *
 * Blocks are grouped by measure and coloured by function, so the shape of
 * the progression - where it leaves home, builds tension and resolves - is
 * readable at a glance, and resolution arrows show which dominants land
 * where.
 */
export function HarmonyRibbon({
  pages,
  cadences,
  keyInfo,
  hovered,
  selected,
  onHover,
  onSelect,
}: Props) {
  const chords = useMemo(() => pages.flatMap((page) => page.chords), [pages]);

  const cadenceByChord = useMemo(() => {
    const map = new Map<string, Cadence>();
    cadences.forEach((cadence) => map.set(cadence.chordId, cadence));
    return map;
  }, [cadences]);

  const groups = useMemo(() => {
    const byMeasure: { measure: number; page: number; chords: Chord[] }[] = [];
    chords.forEach((chord) => {
      const last = byMeasure[byMeasure.length - 1];
      if (last && last.measure === chord.measure && last.page === chord.page) {
        last.chords.push(chord);
      } else {
        byMeasure.push({ measure: chord.measure, page: chord.page, chords: [chord] });
      }
    });
    return byMeasure;
  }, [chords]);

  if (!chords.length) return null;

  return (
    <section className="ribbon">
      <header className="ribbon-head">
        <div>
          <h2>Harmonic map</h2>
          <p>
            {keyInfo ? (
              <>
                Everything is read in <strong>{keyInfo.name}</strong>. Colour shows what each
                chord is doing; arrows show a dominant resolving.
              </>
            ) : (
              'Colour shows what each chord is doing.'
            )}
          </p>
        </div>
      </header>

      <div className="ribbon-track">
        {groups.map((group) => {
          const cadence = group.chords
            .map((chord) => cadenceByChord.get(chord.id))
            .find(Boolean);
          return (
            <div className="ribbon-measure" key={`${group.page}-${group.measure}`}>
              <div className="ribbon-measure-label">
                <span>{group.chords[0]?.measureNumber ?? group.measure + 1}</span>
              </div>

              <div className="ribbon-blocks">
                {group.chords.map((chord) => {
                  const color = colorFor(chord.function);
                  const tier = confidenceTier(chord.confidence);
                  const isActive = chord.id === (selected ?? hovered);
                  const resolves =
                    chord.function === 'dominant' || chord.function === 'secondary-dominant';

                  return (
                    <button
                      type="button"
                      key={chord.id}
                      className={`ribbon-block tier-${tier} ${isActive ? 'is-active' : ''}`}
                      style={{
                        flexGrow: Math.max(1, chord.beats || 1),
                        background: `linear-gradient(180deg, ${alpha(color, 0.9)}, ${alpha(
                          color,
                          0.55,
                        )})`,
                        boxShadow: isActive ? `0 0 0 2px ${color}, 0 8px 24px ${alpha(color, 0.4)}` : undefined,
                      }}
                      onMouseEnter={() => onHover(chord.id)}
                      onMouseLeave={() => onHover(null)}
                      onClick={() => onSelect(selected === chord.id ? null : chord.id)}
                      title={`${chord.symbol} - ${chord.roman}`}
                    >
                      <span className="ribbon-roman">{chord.roman}</span>
                      <span className="ribbon-symbol">{chord.symbol}</span>
                      {tier !== 'high' && (
                        <span className="ribbon-confidence">
                          {Math.round(chord.confidence * 100)}%
                        </span>
                      )}
                      {resolves && <span className="ribbon-arrow">→</span>}
                    </button>
                  );
                })}
              </div>

              {cadence && (
                <div className="ribbon-cadence">
                  <span>{cadence.progression ?? cadence.label}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
