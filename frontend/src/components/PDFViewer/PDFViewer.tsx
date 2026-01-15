import { useCallback, useEffect, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { useStore } from '../../store/useStore';
import Overlay from '../Overlay/Overlay';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';
import './PDFViewer.css';

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

export default function PDFViewer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(800);

  const {
    pdfUrl,
    currentPage,
    totalPages,
    scale,
    analysis,
    isAnalyzing,
    showSidebar,
    setCurrentPage,
    setTotalPages,
    setScale,
    toggleSidebar,
    reset,
  } = useStore();

  // Handle container resize
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        const sidebarWidth = showSidebar ? 350 : 0;
        setContainerWidth(window.innerWidth - sidebarWidth - 48);
      }
    };

    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, [showSidebar]);

  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setTotalPages(numPages);
  }, [setTotalPages]);

  const handlePrevPage = useCallback(() => {
    setCurrentPage(Math.max(1, currentPage - 1));
  }, [currentPage, setCurrentPage]);

  const handleNextPage = useCallback(() => {
    setCurrentPage(Math.min(totalPages, currentPage + 1));
  }, [currentPage, totalPages, setCurrentPage]);

  const handleZoomIn = useCallback(() => {
    setScale(scale + 0.25);
  }, [scale, setScale]);

  const handleZoomOut = useCallback(() => {
    setScale(scale - 0.25);
  }, [scale, setScale]);

  const handleReset = useCallback(() => {
    if (confirm('Close this document and upload a new one?')) {
      reset();
    }
  }, [reset]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') handlePrevPage();
      if (e.key === 'ArrowRight') handleNextPage();
      if (e.key === '+' || e.key === '=') handleZoomIn();
      if (e.key === '-') handleZoomOut();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handlePrevPage, handleNextPage, handleZoomIn, handleZoomOut]);

  const pageAnalysis = analysis?.pages.find(p => p.pageNumber === currentPage);

  return (
    <div className="pdf-viewer" ref={containerRef}>
      {/* Toolbar */}
      <div className="pdf-toolbar">
        <div className="toolbar-left">
          <button onClick={handleReset} className="toolbar-btn" title="Upload new file">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
              <path d="M3 3v5h5" />
            </svg>
          </button>
          <span className="toolbar-filename">{useStore.getState().pdfFile?.name || 'Sheet Music'}</span>
        </div>

        <div className="toolbar-center">
          <button onClick={handlePrevPage} disabled={currentPage <= 1} className="toolbar-btn">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
          <span className="page-indicator">
            Page {currentPage} of {totalPages || '?'}
          </span>
          <button onClick={handleNextPage} disabled={currentPage >= totalPages} className="toolbar-btn">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </div>

        <div className="toolbar-right">
          <button onClick={handleZoomOut} className="toolbar-btn" title="Zoom out">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="8" y1="11" x2="14" y2="11" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </button>
          <span className="zoom-level">{Math.round(scale * 100)}%</span>
          <button onClick={handleZoomIn} className="toolbar-btn" title="Zoom in">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="11" y1="8" x2="11" y2="14" />
              <line x1="8" y1="11" x2="14" y2="11" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </button>
          <button onClick={toggleSidebar} className="toolbar-btn" title="Toggle sidebar">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <line x1="15" y1="3" x2="15" y2="21" />
            </svg>
          </button>
        </div>
      </div>

      {/* PDF Content */}
      <div className="pdf-content">
        {isAnalyzing && (
          <div className="analyzing-overlay">
            <div className="analyzing-spinner" />
            <p>Analyzing sheet music...</p>
          </div>
        )}

        <div className="pdf-page-container">
          <Document
            file={pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            loading={<div className="pdf-loading">Loading PDF...</div>}
            error={<div className="pdf-error">Failed to load PDF</div>}
          >
            <div className="pdf-page-wrapper">
              <Page
                pageNumber={currentPage}
                width={containerWidth * scale}
                renderTextLayer={false}
                renderAnnotationLayer={false}
              />
              {pageAnalysis && !isAnalyzing && (
                <Overlay
                  measures={pageAnalysis.measures}
                  modulations={analysis?.modulations.filter(m =>
                    m.measureNumber >= (pageAnalysis.measures[0]?.number || 1) &&
                    m.measureNumber <= (pageAnalysis.measures[pageAnalysis.measures.length - 1]?.number || 1)
                  ) || []}
                />
              )}
            </div>
          </Document>
        </div>
      </div>

      {/* Key indicator */}
      {analysis && (
        <div className="key-indicator">
          <span className="key-label">Key:</span>
          <span className="key-value">
            {analysis.globalKey.tonic} {analysis.globalKey.mode}
          </span>
        </div>
      )}
    </div>
  );
}
