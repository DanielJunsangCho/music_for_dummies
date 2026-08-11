import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchAnalysis, pollAnalysis, uploadPdf } from './api';
import { ChordInspector } from './components/ChordInspector';
import { HarmonyRibbon } from './components/HarmonyRibbon';
import { ScoreView } from './components/ScoreView';
import { TopBar } from './components/TopBar';
import { UploadScreen } from './components/UploadScreen/UploadScreen';
import type { Analysis, Chord } from './types';

export default function App() {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [filename, setFilename] = useState('Score');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [showMeasures, setShowMeasures] = useState(false);

  const watch = useCallback((id: string) => {
    return pollAnalysis(id, (next) => {
      setAnalysis(next);
      if (next.status === 'error') setError(next.error ?? 'Analysis failed');
      if (next.status !== 'running' && next.status !== 'queued') setBusy(false);
    });
  }, []);

  // Deep link for revisiting a score: ?id=<upload-id>
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('id');
    if (!id) return;
    let stop: (() => void) | undefined;
    void fetchAnalysis(id)
      .then((initial) => {
        setAnalysis(initial);
        if (initial.status === 'running' || initial.status === 'queued') {
          setBusy(true);
          stop = watch(id);
        }
      })
      .catch(() => setError('Could not load that analysis'));
    return () => stop?.();
  }, [watch]);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      setBusy(true);
      setFilename(file.name.replace(/\.pdf$/i, ''));
      try {
        const { id } = await uploadPdf(file);
        const url = new URL(window.location.href);
        url.searchParams.set('id', id);
        window.history.replaceState({}, '', url);
        watch(id);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed');
        setBusy(false);
      }
    },
    [watch],
  );

  const pages = useMemo(() => analysis?.pages ?? [], [analysis?.pages]);
  const chords = useMemo(() => pages.flatMap((page) => page.chords), [pages]);

  const activeChord: Chord | null = useMemo(() => {
    const id = selected ?? hovered;
    return chords.find((chord) => chord.id === id) ?? null;
  }, [chords, hovered, selected]);

  const nextChord: Chord | null = useMemo(() => {
    if (!activeChord) return null;
    const index = chords.findIndex((chord) => chord.id === activeChord.id);
    return index >= 0 && index + 1 < chords.length ? chords[index + 1] : null;
  }, [activeChord, chords]);

  const activeCadence = useMemo(
    () => analysis?.cadences?.find((c) => c.chordId === activeChord?.id) ?? null,
    [analysis?.cadences, activeChord],
  );

  const reset = useCallback(() => {
    setAnalysis(null);
    setSelected(null);
    setHovered(null);
    setError(null);
    const url = new URL(window.location.href);
    url.searchParams.delete('id');
    window.history.replaceState({}, '', url);
  }, []);

  if (!analysis || (!pages.length && analysis.status !== 'error')) {
    return (
      <UploadScreen
        onFile={handleFile}
        error={error}
        busy={busy || analysis?.status === 'running'}
      />
    );
  }

  return (
    <div className="app">
      <TopBar
        analysis={analysis}
        filename={filename}
        zoom={zoom}
        onZoom={setZoom}
        showMeasures={showMeasures}
        onToggleMeasures={setShowMeasures}
        onReset={reset}
      />

      <main className="workspace">
        <ScoreView
          pages={pages}
          zoom={zoom}
          hovered={hovered}
          selected={selected}
          onHover={setHovered}
          onSelect={setSelected}
          showMeasures={showMeasures}
        />
        <ChordInspector
          chord={activeChord}
          next={nextChord}
          cadence={activeCadence}
          pages={pages}
          keyInfo={analysis.key}
          meter={analysis.meter}
        />
      </main>

      <HarmonyRibbon
        pages={pages}
        cadences={analysis.cadences ?? []}
        keyInfo={analysis.key}
        hovered={hovered}
        selected={selected}
        onHover={setHovered}
        onSelect={setSelected}
      />
    </div>
  );
}
