import { useCallback } from 'react';
import { useStore } from '../../store/useStore';
import { getChordFunctionColor } from '../../utils/mockData';
import type { ChordAnalysis, Measure, Modulation, HoverTarget } from '../../types/music';
import './Overlay.css';

interface OverlayProps {
  measures: Measure[];
  modulations: Modulation[];
}

export default function Overlay({ measures, modulations }: OverlayProps) {
  const { setHoverTarget, setSelectedMeasure, selectedMeasure } = useStore();

  const handleChordHover = useCallback((
    chord: ChordAnalysis,
    event: React.MouseEvent
  ) => {
    const target: HoverTarget = {
      type: 'chord',
      data: chord,
      position: { x: event.clientX, y: event.clientY },
    };
    setHoverTarget(target);
  }, [setHoverTarget]);

  const handleMeasureHover = useCallback((
    measure: Measure,
    event: React.MouseEvent
  ) => {
    const target: HoverTarget = {
      type: 'measure',
      data: measure,
      position: { x: event.clientX, y: event.clientY },
    };
    setHoverTarget(target);
  }, [setHoverTarget]);

  const handleModulationHover = useCallback((
    modulation: Modulation,
    event: React.MouseEvent
  ) => {
    const target: HoverTarget = {
      type: 'modulation',
      data: modulation,
      position: { x: event.clientX, y: event.clientY },
    };
    setHoverTarget(target);
  }, [setHoverTarget]);

  const handleMouseLeave = useCallback(() => {
    setHoverTarget(null);
  }, [setHoverTarget]);

  const handleMeasureClick = useCallback((measureNumber: number) => {
    setSelectedMeasure(selectedMeasure === measureNumber ? null : measureNumber);
  }, [selectedMeasure, setSelectedMeasure]);

  return (
    <div className="overlay">
      {/* Measure overlays */}
      {measures.map((measure) => (
        <div
          key={`measure-${measure.number}`}
          className={`measure-overlay ${selectedMeasure === measure.number ? 'selected' : ''}`}
          style={{
            left: `${measure.boundingBox.x * 100}%`,
            top: `${measure.boundingBox.y * 100}%`,
            width: `${measure.boundingBox.width * 100}%`,
            height: `${measure.boundingBox.height * 100}%`,
          }}
          onMouseEnter={(e) => handleMeasureHover(measure, e)}
          onMouseLeave={handleMouseLeave}
          onClick={() => handleMeasureClick(measure.number)}
        >
          <span className="measure-number">{measure.number}</span>

          {/* Chord overlays within measure */}
          {measure.chords.map((chord) => (
            <div
              key={chord.id}
              className="chord-overlay"
              style={{
                left: `${((chord.boundingBox.x - measure.boundingBox.x) / measure.boundingBox.width) * 100}%`,
                top: `${((chord.boundingBox.y - measure.boundingBox.y) / measure.boundingBox.height) * 100}%`,
                width: `${(chord.boundingBox.width / measure.boundingBox.width) * 100}%`,
                height: `${(chord.boundingBox.height / measure.boundingBox.height) * 100}%`,
                borderColor: getChordFunctionColor(chord.function),
              }}
              onMouseEnter={(e) => {
                e.stopPropagation();
                handleChordHover(chord, e);
              }}
              onMouseLeave={handleMouseLeave}
            >
              <div
                className="chord-label"
                style={{ backgroundColor: getChordFunctionColor(chord.function) }}
              >
                {chord.symbol}
              </div>
              <div className="roman-numeral">
                {chord.romanNumeral}
              </div>
            </div>
          ))}
        </div>
      ))}

      {/* Modulation indicators */}
      {modulations.map((mod, idx) => (
        <div
          key={`mod-${idx}`}
          className="modulation-overlay"
          style={{
            left: `${mod.boundingBox.x * 100}%`,
            top: `${mod.boundingBox.y * 100}%`,
            width: `${mod.boundingBox.width * 100}%`,
          }}
          onMouseEnter={(e) => handleModulationHover(mod, e)}
          onMouseLeave={handleMouseLeave}
        >
          <div className="modulation-line" />
          <div className="modulation-label">
            Key change: {mod.fromKey.tonic} → {mod.toKey.tonic}
          </div>
        </div>
      ))}
    </div>
  );
}
