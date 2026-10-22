import React, { useEffect, useState } from 'react';
import { checkHealth, getSystemStatus } from './api/client';
import { HealthResponse, SystemStatusResponse } from './api/types';
import { Header, TabType } from './components/Header';
import { ProjectIdentity } from './components/ProjectIdentity';
import { SystemPipeline } from './components/SystemPipeline';
import { PhaseTimeline } from './components/PhaseTimeline';
import { ModuleRoadmap } from './components/ModuleRoadmap';
import { TechnicalHealth } from './components/TechnicalHealth';
import { Sender } from './pages/Sender';
import { Receiver } from './pages/Receiver';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastCheck, setLastCheck] = useState<Date | null>(null);

  const fetchStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthData, statusData] = await Promise.all([
        checkHealth(),
        getSystemStatus()
      ]);
      setHealth(healthData);
      setStatus(statusData);
      setLastCheck(new Date());
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to connect to backend API server.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  return (
    <div className="min-h-screen bg-canvas-base text-canvas-textPrimary flex flex-col font-sans selection:bg-accent/20 selection:text-white">
      {/* Top App Header & Compact Navigation */}
      <Header 
        health={health} 
        loading={loading} 
        onRefresh={fetchStatus}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
      />

      {/* Main Research Workbench Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {activeTab === 'overview' && (
          <div className="space-y-6 sm:space-y-7">
            {/* 1. Research Identity & Hypothesis Objective */}
            <ProjectIdentity 
              currentPhase={status?.current_phase || 4} 
            />

            {/* 2. System Pipeline Architecture (Implemented vs. Planned) */}
            <SystemPipeline />

            {/* 3. Phase Timeline & Technical Verification */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              <div className="lg:col-span-7">
                <PhaseTimeline />
              </div>
              <div className="lg:col-span-5">
                <TechnicalHealth 
                  health={health} 
                  error={error} 
                  lastCheck={lastCheck} 
                />
              </div>
            </div>

            {/* 4. Backend Module Lifecycle Roadmap (Live from /api/status) */}
            <ModuleRoadmap 
              modules={status?.modules} 
              loading={loading} 
            />
          </div>
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
            <span className="text-emerald-500 font-medium">Phase 4 Audio & Image Steganography Verified</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
