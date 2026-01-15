import { useEffect, useRef, useState } from 'react';
import type { HoverTarget, ChordAnalysis, Measure, Modulation } from '../../types/music';
import { getChordFunctionColor, getChordFunctionDescription } from '../../utils/mockData';
import './Tooltip.css';

interface TooltipProps {
  target: HoverTarget;
}

export default function Tooltip({ target }: TooltipProps) {
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (!tooltipRef.current) return;

    const tooltip = tooltipRef.current;
    const rect = tooltip.getBoundingClientRect();
    const padding = 16;

    let x = target.position.x + 16;
    let y = target.position.y + 16;

    // Prevent overflow on the right
    if (x + rect.width > window.innerWidth - padding) {
      x = target.position.x - rect.width - 16;
    }

    // Prevent overflow on the bottom
    if (y + rect.height > window.innerHeight - padding) {
      y = target.position.y - rect.height - 16;
    }

    // Ensure minimum position
    x = Math.max(padding, x);
    y = Math.max(padding, y);

    setPosition({ x, y });
  }, [target.position]);

  const renderContent = () => {
    switch (target.type) {
      case 'chord':
        return <ChordTooltip chord={target.data as ChordAnalysis} />;
      case 'measure':
        return <MeasureTooltip measure={target.data as Measure} />;
      case 'modulation':
        return <ModulationTooltip modulation={target.data as Modulation} />;
      default:
        return null;
    }
  };

  return (
    <div
      ref={tooltipRef}
      className="tooltip"
      style={{
        left: position.x,
        top: position.y,
      }}
    >
      {renderContent()}
    </div>
  );
}

function ChordTooltip({ chord }: { chord: ChordAnalysis }) {
  const functionColor = getChordFunctionColor(chord.function);
  const functionDesc = getChordFunctionDescription(chord.function);

  return (
    <div className="tooltip-content">
      <div className="tooltip-header">
        <h3 className="tooltip-title">{chord.symbol}</h3>
        <span
          className="tooltip-badge"
          style={{ backgroundColor: functionColor }}
        >
          {chord.romanNumeral}
        </span>
      </div>

      <div className="tooltip-section">
        <div className="tooltip-row">
          <span className="tooltip-label">Notes</span>
          <span className="tooltip-value">{chord.notes.join(' - ')}</span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Root</span>
          <span className="tooltip-value">{chord.root}</span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Quality</span>
          <span className="tooltip-value">{chord.quality || 'major'}</span>
        </div>
        {chord.bass && (
          <div className="tooltip-row">
            <span className="tooltip-label">Bass Note</span>
            <span className="tooltip-value">{chord.bass}</span>
          </div>
        )}
      </div>

      <div className="tooltip-section">
        <div className="tooltip-row">
          <span className="tooltip-label">Function</span>
          <span
            className="tooltip-function"
            style={{ color: functionColor }}
          >
            {chord.function.replace('_', ' ')}
          </span>
        </div>
        <p className="tooltip-explanation">{functionDesc}</p>
      </div>

      <div className="tooltip-confidence">
        <span className="tooltip-label">Confidence</span>
        <div className="confidence-bar">
          <div
            className="confidence-fill"
            style={{ width: `${chord.confidence * 100}%` }}
          />
        </div>
        <span className="confidence-value">{Math.round(chord.confidence * 100)}%</span>
      </div>
    </div>
  );
}

function MeasureTooltip({ measure }: { measure: Measure }) {
  return (
    <div className="tooltip-content">
      <div className="tooltip-header">
        <h3 className="tooltip-title">Measure {measure.number}</h3>
        <span className="tooltip-badge secondary">
          {measure.timeSignature.numerator}/{measure.timeSignature.denominator}
        </span>
      </div>

      <div className="tooltip-section">
        <div className="tooltip-row">
          <span className="tooltip-label">Key</span>
          <span className="tooltip-value">
            {measure.localKey.tonic} {measure.localKey.mode}
          </span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Chords</span>
          <span className="tooltip-value">
            {measure.chords.length > 0
              ? measure.chords.map(c => c.symbol).join(' → ')
              : 'No chords detected'}
          </span>
        </div>
      </div>

      {measure.chords.length > 0 && (
        <div className="tooltip-section">
          <span className="tooltip-label">Harmonic Analysis</span>
          <div className="harmonic-analysis">
            {measure.chords.map((chord, idx) => (
              <div key={idx} className="harmonic-chord">
                <span
                  className="harmonic-roman"
                  style={{ color: getChordFunctionColor(chord.function) }}
                >
                  {chord.romanNumeral}
                </span>
                <span className="harmonic-symbol">{chord.symbol}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ModulationTooltip({ modulation }: { modulation: Modulation }) {
  return (
    <div className="tooltip-content modulation">
      <div className="tooltip-header">
        <h3 className="tooltip-title">Key Change</h3>
        <span className="tooltip-badge modulation-badge">
          Measure {modulation.measureNumber}
        </span>
      </div>

      <div className="tooltip-section">
        <div className="modulation-keys">
          <div className="key-box from">
            <span className="key-label">From</span>
            <span className="key-name">
              {modulation.fromKey.tonic} {modulation.fromKey.mode}
            </span>
          </div>
          <div className="modulation-arrow">→</div>
          <div className="key-box to">
            <span className="key-label">To</span>
            <span className="key-name">
              {modulation.toKey.tonic} {modulation.toKey.mode}
            </span>
          </div>
        </div>
      </div>

      {modulation.pivotChord && (
        <div className="tooltip-section">
          <div className="tooltip-row">
            <span className="tooltip-label">Pivot Chord</span>
            <span className="tooltip-value">{modulation.pivotChord.symbol}</span>
          </div>
        </div>
      )}

      <div className="tooltip-section">
        <span className="tooltip-label">Analysis</span>
        <p className="tooltip-explanation">{modulation.reasoning}</p>
      </div>
    </div>
  );
}
