import React, { useState } from 'react';
import { Header, TabType } from './components/Header';
import { Sender } from './pages/Sender';
import { Receiver } from './pages/Receiver';
import { MultimodalTriad } from './pages/MultimodalTriad';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('triad');

  return (
    <div className="min-h-screen bg-canvas-base text-canvas-textPrimary flex flex-col font-sans selection:bg-accent/20 selection:text-white">
      {/* Top App Header & Clean Navigation */}
      <Header 
        activeTab={activeTab}
        onSelectTab={setActiveTab}
      />

      {/* Main Research Workbench Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {activeTab === 'triad' && (
          <MultimodalTriad />
        )}

        {activeTab === 'sender' && (
          <Sender />
        )}

        {activeTab === 'receiver' && (
          <Receiver />
        )}
      </main>

      {/* Minimal Academic Footer */}
      <footer className="border-t border-canvas-border bg-canvas-surface py-5 mt-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-xs text-canvas-textMuted font-mono gap-2">
          <div>
            Reliability-Aware Adaptive Multimodal Steganography Research Platform
          </div>
          <div className="flex items-center space-x-3 text-[11px]">
            <span>FastAPI • React 18 • Pytest</span>
            <span>•</span>
            <span className="text-emerald-500 font-medium">Verified System</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
