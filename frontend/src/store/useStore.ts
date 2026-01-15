import { create } from 'zustand';
import type { AnalysisResult, HoverTarget, Key } from '../types/music';

interface AppState {
  // PDF State
  pdfFile: File | null;
  pdfUrl: string | null;
  currentPage: number;
  totalPages: number;
  scale: number;

  // Analysis State
  analysis: AnalysisResult | null;
  isAnalyzing: boolean;
  analysisProgress: number;

  // UI State
  hoverTarget: HoverTarget | null;
  selectedMeasure: number | null;
  showSidebar: boolean;
  currentKey: Key | null;

  // Actions
  setPdfFile: (file: File | null) => void;
  setPdfUrl: (url: string | null) => void;
  setCurrentPage: (page: number) => void;
  setTotalPages: (pages: number) => void;
  setScale: (scale: number) => void;
  setAnalysis: (analysis: AnalysisResult | null) => void;
  setIsAnalyzing: (isAnalyzing: boolean) => void;
  setAnalysisProgress: (progress: number) => void;
  setHoverTarget: (target: HoverTarget | null) => void;
  setSelectedMeasure: (measure: number | null) => void;
  toggleSidebar: () => void;
  setCurrentKey: (key: Key | null) => void;
  reset: () => void;
}

const initialState = {
  pdfFile: null,
  pdfUrl: null,
  currentPage: 1,
  totalPages: 0,
  scale: 1.0,
  analysis: null,
  isAnalyzing: false,
  analysisProgress: 0,
  hoverTarget: null,
  selectedMeasure: null,
  showSidebar: true,
  currentKey: null,
};

export const useStore = create<AppState>((set) => ({
  ...initialState,

  setPdfFile: (file) => set({ pdfFile: file }),
  setPdfUrl: (url) => set({ pdfUrl: url }),
  setCurrentPage: (page) => set({ currentPage: page }),
  setTotalPages: (pages) => set({ totalPages: pages }),
  setScale: (scale) => set({ scale: Math.max(0.5, Math.min(3, scale)) }),
  setAnalysis: (analysis) => set({
    analysis,
    currentKey: analysis?.globalKey || null
  }),
  setIsAnalyzing: (isAnalyzing) => set({ isAnalyzing }),
  setAnalysisProgress: (progress) => set({ analysisProgress: progress }),
  setHoverTarget: (target) => set({ hoverTarget: target }),
  setSelectedMeasure: (measure) => set({ selectedMeasure: measure }),
  toggleSidebar: () => set((state) => ({ showSidebar: !state.showSidebar })),
  setCurrentKey: (key) => set({ currentKey: key }),
  reset: () => set(initialState),
}));
