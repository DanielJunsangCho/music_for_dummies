import { useCallback, useRef, useState } from 'react';
import { useStore } from '../../store/useStore';
import { uploadPdf, getAnalysis } from '../../api/analysis';
import { generateMockAnalysis } from '../../utils/mockData';
import './UploadScreen.css';

export default function UploadScreen() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const { setPdfFile, setPdfUrl, setAnalysis, setIsAnalyzing, setTotalPages, setAnalysisProgress } = useStore();

  const handleFile = useCallback(async (file: File) => {
    if (file.type !== 'application/pdf') {
      alert('Please upload a PDF file');
      return;
    }

    setPdfFile(file);
    const url = URL.createObjectURL(file);
    setPdfUrl(url);
    setIsAnalyzing(true);
    setStatusMessage('Uploading PDF...');

    try {
      // Upload to backend
      const { id } = await uploadPdf(file);
      setStatusMessage('Running OMR analysis (this may take 1-2 minutes)...');
      setAnalysisProgress(0.2);

      // Poll for analysis results
      let attempts = 0;
      const maxAttempts = 60; // 2 minutes max

      const pollAnalysis = async (): Promise<void> => {
        try {
          const result = await getAnalysis(id);

          if (result.status === 'completed') {
            setAnalysis(result);
            setTotalPages(result.pages?.length || 1);
            setIsAnalyzing(false);
            setStatusMessage('');
            return;
          } else if (result.status === 'error') {
            throw new Error(result.error || 'Analysis failed');
          }

          // Still processing, poll again
          attempts++;
          if (attempts < maxAttempts) {
            setAnalysisProgress(0.2 + (attempts / maxAttempts) * 0.7);
            setStatusMessage(`Analyzing... (${Math.round((attempts / maxAttempts) * 100)}%)`);
            setTimeout(pollAnalysis, 2000);
          } else {
            throw new Error('Analysis timed out');
          }
        } catch (err) {
          // If 404, analysis not ready yet
          attempts++;
          if (attempts < maxAttempts) {
            setTimeout(pollAnalysis, 2000);
          } else {
            throw err;
          }
        }
      };

      // Start polling after a short delay
      setTimeout(pollAnalysis, 3000);

    } catch (error) {
      console.error('Backend upload failed, using mock data:', error);
      setStatusMessage('Backend unavailable, using demo mode...');

      // Fallback to mock data
      setTimeout(() => {
        const mockAnalysis = generateMockAnalysis(file.name);
        setAnalysis(mockAnalysis);
        setTotalPages(mockAnalysis.pages.length);
        setIsAnalyzing(false);
        setStatusMessage('');
      }, 1500);
    }
  }, [setPdfFile, setPdfUrl, setAnalysis, setIsAnalyzing, setTotalPages, setAnalysisProgress]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (file) {
      handleFile(file);
    }
  }, [handleFile]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFile(file);
    }
  }, [handleFile]);

  return (
    <div className="upload-screen">
      <div className="upload-content">
        <h1 className="upload-title">Music for Dummies</h1>
        <p className="upload-subtitle">
          Upload sheet music to learn music theory interactively
        </p>

        <div
          className={`upload-zone ${isDragging ? 'dragging' : ''}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={handleClick}
        >
          <div className="upload-icon">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="12" y1="18" x2="12" y2="12" />
              <line x1="9" y1="15" x2="15" y2="15" />
            </svg>
          </div>
          <p className="upload-text">
            Drop your PDF sheet music here
          </p>
          <p className="upload-hint">
            or click to browse
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={handleFileChange}
          />
        </div>

        {statusMessage && (
          <div className="status-message">
            <div className="status-spinner" />
            <span>{statusMessage}</span>
          </div>
        )}

        <div className="upload-features">
          <div className="feature">
            <span className="feature-icon">♯</span>
            <span>Chord Detection</span>
          </div>
          <div className="feature">
            <span className="feature-icon">♭</span>
            <span>Key Analysis</span>
          </div>
          <div className="feature">
            <span className="feature-icon">VII</span>
            <span>Roman Numerals</span>
          </div>
        </div>
      </div>
    </div>
  );
}
