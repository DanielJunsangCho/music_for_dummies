import type { Analysis } from '../types';
import { FUNCTION_LABELS, FUNCTION_ORDER, colorFor } from '../theme';

interface Props {
  analysis: Analysis;
  filename: string;
  zoom: number;
  onZoom: (value: number) => void;
  showMeasures: boolean;
  onToggleMeasures: (value: boolean) => void;
  onReset: () => void;
}

export function TopBar({
  analysis,
  filename,
  zoom,
  onZoom,
  showMeasures,
  onToggleMeasures,
  onReset,
}: Props) {
  const { key, keys, meter, stats, progress, status, source } = analysis;
  const busy = status === 'running' || status === 'queued';
  const localKeys = keys?.length ? keys : key ? [key] : [];
  const multiKey = localKeys.length > 1;
  const readAs =
    source === 'engraved'
      ? 'Read from the engraving itself, so every pitch is exact.'
      : source === 'mixed'
        ? 'Part read from the engraving, part recognised from the scan.'
        : 'Recognised from a scan, so a few notes may be misread.';

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="ghost" onClick={onReset} title="Analyse another file">
          ←
        </button>
        <div className="title-block">
          <h1>{filename}</h1>
          <div className="meta-row">
            {key && (
              <span
                className="key-pill"
                title={
                  multiKey
                    ? `Local keys: ${localKeys.map((item) => item.name).join(' · ')}`
                    : undefined
                }
              >
                {multiKey ? `${localKeys.length} keys` : key.name}
                {!multiKey && key.sharps != null && key.sharps !== 0 && (
                  <em>
                    {Math.abs(key.sharps)}
                    {key.sharps > 0 ? '♯' : '♭'}
                  </em>
                )}
              </span>
            )}
            {meter?.numerator && meter.denominator && (
              <span className="meter-pill" title="Time signature">
                {meter.numerator}/{meter.denominator}
              </span>
            )}
            {stats && (
              <span className="muted">
                {stats.measures} measures · {stats.chords} chords · {stats.notes} notes
              </span>
            )}
            {source && (
              <span className={`source-pill source-${source}`} title={readAs}>
                {source === 'scanned' ? 'scan' : source}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="legend">
        {FUNCTION_ORDER.map((fn) => (
          <span key={fn} className="legend-item">
            <i style={{ background: colorFor(fn) }} />
            {FUNCTION_LABELS[fn]}
          </span>
        ))}
      </div>

      <div className="topbar-right">
        {busy && (
          <span className="progress-pill">
            <i className="spinner" />
            {progress.stage} ({progress.pagesDone}/{progress.pagesTotal})
          </span>
        )}
        <label className="toggle">
          <input
            type="checkbox"
            checked={showMeasures}
            onChange={(event) => onToggleMeasures(event.target.checked)}
          />
          Measures
        </label>
        <label className="zoom">
          <input
            type="range"
            min={60}
            max={220}
            value={zoom}
            onChange={(event) => onZoom(Number(event.target.value))}
          />
          {zoom}%
        </label>
      </div>
    </header>
  );
}
