import { useEffect, useMemo, useRef } from 'react';
import type { Chord, Page } from '../types';
import { alpha, colorFor, confidenceTier } from '../theme';

interface Props {
  pages: Page[];
  zoom: number;
  hovered: string | null;
  selected: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string | null) => void;
  showMeasures: boolean;
}

/**
 * The score, with chord regions and noteheads anchored to the exact pixels
 * the analysis found them at. The image shown is the same image that was
 * analysed, so a box can never drift from the ink underneath it.
 */
export function ScoreView({
  pages,
  zoom,
  hovered,
  selected,
  onHover,
  onSelect,
  showMeasures,
}: Props) {
  const active = selected ?? hovered;
  const containerRef = useRef<HTMLDivElement>(null);

  const activeChord = useMemo(() => {
    if (!active) return null;
    for (const page of pages) {
      const found = page.chords.find((c) => c.id === active);
      if (found) return found;
    }
    return null;
  }, [active, pages]);

  useEffect(() => {
    if (!selected || !containerRef.current) return;
    const element = containerRef.current.querySelector(`[data-chord="${selected}"]`);
    element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [selected]);

  return (
    <div className="score-scroll" ref={containerRef}>
      <div className="score-stack" style={{ width: `${zoom}%` }}>
        {pages.map((page) => (
          <PageLayer
            key={page.page}
            page={page}
            activeChord={activeChord}
            hovered={hovered}
            selected={selected}
            onHover={onHover}
            onSelect={onSelect}
            showMeasures={showMeasures}
          />
        ))}
      </div>
    </div>
  );
}

interface LayerProps {
  page: Page;
  activeChord: Chord | null;
  hovered: string | null;
  selected: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string | null) => void;
  showMeasures: boolean;
}

function PageLayer({
  page,
  activeChord,
  hovered,
  selected,
  onHover,
  onSelect,
  showMeasures,
}: LayerProps) {
  const activeNotes = useMemo(
    () => new Set(activeChord?.page === page.page ? activeChord.notes : []),
    [activeChord, page.page],
  );

  const pct = (value: number) => `${value * 100}%`;

  return (
    <figure className="page">
      <img src={page.image} alt={`Page ${page.page}`} draggable={false} />

      <div className="page-overlay">
        {showMeasures &&
          page.measures.map((measure) => (
            <div
              key={`m${measure.index}`}
              className="measure-outline"
              style={{
                left: pct(measure.x),
                top: pct(measure.y),
                width: pct(measure.width),
                height: pct(measure.height),
              }}
            >
              <span>{measure.number}</span>
            </div>
          ))}

        {page.chords.map((chord) => {
          const color = colorFor(chord.function);
          const tier = confidenceTier(chord.confidence);
          const isActive = chord.id === (selected ?? hovered);
          const isDimmed = Boolean(selected ?? hovered) && !isActive;

          return (
            <div
              key={chord.id}
              data-chord={chord.id}
              className={`chord-region tier-${tier} ${isActive ? 'is-active' : ''} ${
                isDimmed ? 'is-dimmed' : ''
              }`}
              style={{
                left: pct(chord.box.x),
                top: pct(chord.box.y),
                width: pct(chord.box.width),
                height: pct(chord.box.height),
                background: `linear-gradient(180deg, ${alpha(color, isActive ? 0.3 : 0.14)}, ${alpha(
                  color,
                  isActive ? 0.16 : 0.05,
                )})`,
                borderColor: alpha(color, isActive ? 0.95 : 0.5),
              }}
              onMouseEnter={() => onHover(chord.id)}
              onMouseLeave={() => onHover(null)}
              onClick={() => onSelect(selected === chord.id ? null : chord.id)}
            />
          );
        })}

        {/* Chips live outside the regions: a region is blended into the page
            with multiply, and a child label would be washed out by it. They
            sit on the lane the backend measured for each system, which is
            where a lead sheet puts its chord symbols. */}
        {page.chords.map((chord) => {
          const color = colorFor(chord.function);
          const tier = confidenceTier(chord.confidence);
          const isActive = chord.id === (selected ?? hovered);
          const isDimmed = Boolean(selected ?? hovered) && !isActive;
          const system = page.systems.find((s) => s.index === chord.system);
          const lane = system ? system.labelLane : chord.box.y;

          return (
            <button
              type="button"
              key={`chip-${chord.id}`}
              className={`chord-chip tier-${tier} ${isActive ? 'is-active' : ''} ${
                isDimmed ? 'is-dimmed' : ''
              }`}
              style={{
                left: pct(chord.box.x),
                top: pct(Math.max(0, lane)),
                maxWidth: pct(chord.box.width),
                ['--chip-color' as string]: color,
              }}
              onMouseEnter={() => onHover(chord.id)}
              onMouseLeave={() => onHover(null)}
              onFocus={() => onHover(chord.id)}
              onBlur={() => onHover(null)}
              onClick={() => onSelect(selected === chord.id ? null : chord.id)}
            >
              <strong>{chord.symbol}</strong>
              <em>{chord.roman}</em>
              {tier !== 'high' && <i className="chip-flag">{tier === 'low' ? '??' : '?'}</i>}
            </button>
          );
        })}

        {page.notes
          .filter((note) => activeNotes.has(note.id))
          .map((note) => (
            <div
              key={note.id}
              className="note-ring"
              style={{
                left: pct(note.x),
                top: pct(note.y),
                width: pct(note.width),
                height: pct(note.height),
                borderColor: activeChord ? colorFor(activeChord.function) : '#fff',
              }}
            >
              {selected && <span className="note-name">{note.name}</span>}
            </div>
          ))}
      </div>
    </figure>
  );
}
