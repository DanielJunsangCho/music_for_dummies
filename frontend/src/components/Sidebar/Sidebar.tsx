import { useStore } from '../../store/useStore';
import { getChordFunctionColor } from '../../utils/mockData';
import './Sidebar.css';

export default function Sidebar() {
  const { analysis, currentPage, selectedMeasure, setSelectedMeasure, setCurrentPage } = useStore();

  if (!analysis) {
    return (
      <div className="sidebar">
        <div className="sidebar-empty">
          <p>Upload sheet music to see analysis</p>
        </div>
      </div>
    );
  }

  const pageAnalysis = analysis.pages.find(p => p.pageNumber === currentPage);
  const selectedMeasureData = pageAnalysis?.measures.find(m => m.number === selectedMeasure);

  return (
    <div className="sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <h2>Music Analysis</h2>
        <span className="sidebar-filename">{analysis.filename}</span>
      </div>

      {/* Global Key */}
      <div className="sidebar-section">
        <h3 className="section-title">Key Signature</h3>
        <div className="key-display">
          <span className="key-tonic">{analysis.globalKey.tonic}</span>
          <span className="key-mode">{analysis.globalKey.mode}</span>
        </div>
        {analysis.globalKey.signature !== 0 && (
          <p className="key-info">
            {Math.abs(analysis.globalKey.signature)} {analysis.globalKey.signature > 0 ? 'sharp' : 'flat'}
            {Math.abs(analysis.globalKey.signature) !== 1 ? 's' : ''}
          </p>
        )}
      </div>

      {/* Chord Progression */}
      <div className="sidebar-section">
        <h3 className="section-title">Chord Progression</h3>
        {analysis.chordProgression.commonName && (
          <p className="progression-name">{analysis.chordProgression.commonName}</p>
        )}
        <div className="progression-grid">
          {analysis.chordProgression.romanNumerals.map((numeral, idx) => (
            <button
              key={idx}
              className={`progression-chord ${selectedMeasure === idx + 1 ? 'active' : ''}`}
              onClick={() => {
                setSelectedMeasure(idx + 1);
                const targetPage = Math.ceil((idx + 1) / 16);
                if (targetPage !== currentPage) {
                  setCurrentPage(targetPage);
                }
              }}
            >
              {numeral}
            </button>
          ))}
        </div>
      </div>

      {/* Modulations */}
      {analysis.modulations.length > 0 && (
        <div className="sidebar-section">
          <h3 className="section-title">Key Changes</h3>
          <div className="modulations-list">
            {analysis.modulations.map((mod, idx) => (
              <div key={idx} className="modulation-item">
                <div className="modulation-header">
                  <span className="modulation-measure">Measure {mod.measureNumber}</span>
                </div>
                <div className="modulation-keys">
                  <span className="mod-from">{mod.fromKey.tonic} {mod.fromKey.mode}</span>
                  <span className="mod-arrow">→</span>
                  <span className="mod-to">{mod.toKey.tonic} {mod.toKey.mode}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Selected Measure Details */}
      {selectedMeasureData && (
        <div className="sidebar-section selected-measure">
          <h3 className="section-title">
            Measure {selectedMeasureData.number} Details
          </h3>
          <div className="measure-details">
            <div className="detail-row">
              <span className="detail-label">Time Signature</span>
              <span className="detail-value">
                {selectedMeasureData.timeSignature.numerator}/{selectedMeasureData.timeSignature.denominator}
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Local Key</span>
              <span className="detail-value">
                {selectedMeasureData.localKey.tonic} {selectedMeasureData.localKey.mode}
              </span>
            </div>
          </div>

          {selectedMeasureData.chords.length > 0 && (
            <div className="measure-chords">
              <h4>Chords in Measure</h4>
              {selectedMeasureData.chords.map((chord, idx) => (
                <div key={idx} className="chord-detail">
                  <div className="chord-detail-header">
                    <span className="chord-symbol">{chord.symbol}</span>
                    <span
                      className="chord-function-badge"
                      style={{ backgroundColor: getChordFunctionColor(chord.function) }}
                    >
                      {chord.function.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="chord-detail-info">
                    <span className="chord-roman">{chord.romanNumeral}</span>
                    <span className="chord-notes">{chord.notes.join(' - ')}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="sidebar-section legend">
        <h3 className="section-title">Function Legend</h3>
        <div className="legend-items">
          <div className="legend-item">
            <span className="legend-color" style={{ backgroundColor: 'var(--accent-tonic)' }} />
            <span>Tonic (I, vi)</span>
          </div>
          <div className="legend-item">
            <span className="legend-color" style={{ backgroundColor: 'var(--accent-predominant)' }} />
            <span>Predominant (ii, IV)</span>
          </div>
          <div className="legend-item">
            <span className="legend-color" style={{ backgroundColor: 'var(--accent-dominant)' }} />
            <span>Dominant (V, V7)</span>
          </div>
          <div className="legend-item">
            <span className="legend-color" style={{ backgroundColor: 'var(--accent-borrowed)' }} />
            <span>Borrowed / Special</span>
          </div>
        </div>
      </div>
    </div>
  );
}
