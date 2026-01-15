import { useCallback } from 'react';
import { useStore } from './store/useStore';
import PDFViewer from './components/PDFViewer/PDFViewer';
import Sidebar from './components/Sidebar/Sidebar';
import Tooltip from './components/Tooltip/Tooltip';
import UploadScreen from './components/UploadScreen/UploadScreen';
import './App.css';

function App() {
  const { pdfUrl, hoverTarget, showSidebar } = useStore();

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      useStore.getState().setHoverTarget(null);
    }
  }, []);

  if (!pdfUrl) {
    return <UploadScreen />;
  }

  return (
    <div className="app" onKeyDown={handleKeyDown} tabIndex={0}>
      <div className="app-content">
        <PDFViewer />
        {showSidebar && <Sidebar />}
      </div>
      {hoverTarget && <Tooltip target={hoverTarget} />}
    </div>
  );
}

export default App;
