import { useCallback, useRef, useState } from 'react';

interface Props {
  onFile: (file: File) => void;
  error?: string | null;
  busy?: boolean;
}

export function UploadScreen({ onFile, error, busy }: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0];
      if (file) onFile(file);
    },
    [onFile],
  );

  return (
    <div className="upload-screen">
      <div className="upload-inner">
        <div className="brand">
          <span className="brand-mark">♪</span>
          <h1>Read the harmony in any score</h1>
          <p>
            Drop in a PDF of sheet music. Every chord gets found, named and explained — anchored
            to the exact notes on the page.
          </p>
        </div>

        <div
          className={`dropzone ${dragging ? 'is-dragging' : ''} ${busy ? 'is-busy' : ''}`}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            handleFiles(event.dataTransfer.files);
          }}
          onClick={() => inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            hidden
            onChange={(event) => handleFiles(event.target.files)}
          />
          <div className="dropzone-icon">{busy ? <i className="spinner big" /> : '⇪'}</div>
          <strong>{busy ? 'Reading the score…' : 'Drop a PDF here'}</strong>
          <span className="muted">or click to choose a file</span>
        </div>

        {error && <p className="error">{error}</p>}

        <ul className="pitch-points">
          <li>
            <b>Exact placement.</b> Chords are anchored to the noteheads that produced them, not
            guessed from beat fractions.
          </li>
          <li>
            <b>Fast.</b> A page is read in well under a second — no neural OMR pass.
          </li>
          <li>
            <b>Honest.</b> Uncertain readings are marked as uncertain instead of hidden.
          </li>
        </ul>
      </div>
    </div>
  );
}
