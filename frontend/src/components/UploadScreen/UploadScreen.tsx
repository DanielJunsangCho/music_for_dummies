import { useCallback, useRef, useState } from 'react';
import { useStore } from '../../store/useStore';
import { generateMockAnalysis } from '../../utils/mockData';
import './UploadScreen.css';

export default function UploadScreen() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const { setPdfFile, setPdfUrl, setAnalysis, setIsAnalyzing, setTotalPages } = useStore();

  const handleFile = useCallback(async (file: File) => {
    if (file.type !== 'application/pdf') {
      alert('Please upload a PDF file');
      return;
    }

    setPdfFile(file);
    const url = URL.createObjectURL(file);
    setPdfUrl(url);
    setIsAnalyzing(true);

    // Simulate analysis with mock data
    // In production, this would call the backend API
    setTimeout(() => {
      const mockAnalysis = generateMockAnalysis(file.name);
      setAnalysis(mockAnalysis);
      setTotalPages(mockAnalysis.pages.length);
      setIsAnalyzing(false);
    }, 1500);
  }, [setPdfFile, setPdfUrl, setAnalysis, setIsAnalyzing, setTotalPages]);

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
