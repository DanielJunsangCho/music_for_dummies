import type { Analysis } from './types';

export async function uploadPdf(file: File): Promise<{ id: string; pages: number }> {
  const body = new FormData();
  body.append('file', file);
  const response = await fetch('/api/upload', { method: 'POST', body });
  if (!response.ok) {
    throw new Error((await response.json().catch(() => ({}))).detail ?? 'Upload failed');
  }
  return response.json();
}

export async function fetchAnalysis(id: string): Promise<Analysis> {
  const response = await fetch(`/api/analysis/${id}`);
  if (!response.ok) throw new Error('Could not load analysis');
  return response.json();
}

/**
 * Poll until the job finishes. The endpoint is read-only, so polling is
 * cheap and never triggers work.
 */
export function pollAnalysis(
  id: string,
  onUpdate: (analysis: Analysis) => void,
  intervalMs = 600,
): () => void {
  let stopped = false;
  let timer: number | undefined;

  const tick = async () => {
    if (stopped) return;
    try {
      const analysis = await fetchAnalysis(id);
      if (stopped) return;
      onUpdate(analysis);
      if (analysis.status === 'complete' || analysis.status === 'error') return;
    } catch {
      // Keep polling through transient failures.
    }
    timer = window.setTimeout(tick, intervalMs);
  };

  void tick();
  return () => {
    stopped = true;
    if (timer) window.clearTimeout(timer);
  };
}
