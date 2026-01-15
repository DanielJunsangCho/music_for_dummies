import axios from 'axios';
import type { AnalysisResult } from '../types/music';

const API_BASE = '/api';

export async function uploadPdf(file: File): Promise<{ id: string }> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await axios.post(`${API_BASE}/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
}

export async function getAnalysis(id: string): Promise<AnalysisResult> {
  const response = await axios.get(`${API_BASE}/analysis/${id}`);
  return response.data;
}

export async function getPageImage(id: string, page: number): Promise<string> {
  const response = await axios.get(`${API_BASE}/page/${id}/${page}`, {
    responseType: 'blob',
  });
  return URL.createObjectURL(response.data);
}

// WebSocket connection for real-time analysis updates
export function connectAnalysisSocket(
  id: string,
  onProgress: (progress: number) => void,
  onComplete: (result: AnalysisResult) => void,
  onError: (error: string) => void
): WebSocket {
  const ws = new WebSocket(`ws://localhost:8000/ws/analysis/${id}`);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'progress') {
      onProgress(data.progress);
    } else if (data.type === 'complete') {
      onComplete(data.result);
    } else if (data.type === 'error') {
      onError(data.message);
    }
  };

  ws.onerror = () => {
    onError('WebSocket connection failed');
  };

  return ws;
}
