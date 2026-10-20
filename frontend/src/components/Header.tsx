import React from 'react';
import { RefreshCw, Activity, Terminal } from 'lucide-react';
import { HealthResponse } from '../api/types';
import { StatusBadge } from './StatusBadge';

interface HeaderProps {
  health: HealthResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

export const Header: React.FC<HeaderProps> = ({ health, loading, onRefresh }) => {
  return (
    <header className="border-b border-canvas-border bg-canvas-surface/95 backdrop-blur-sm sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Top bar */}
        <div className="h-14 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-7 h-7 rounded border border-canvas-border bg-canvas-elevated flex items-center justify-center text-canvas-textSecondary">
              <Terminal className="w-4 h-4 text-accent" />
            </div>
            <div className="flex items-baseline space-x-2">
              <span className="font-mono text-xs font-semibold tracking-wider text-canvas-textPrimary uppercase">
                Adaptive Stego Lab
              </span>
              <span className="text-[11px] font-mono text-canvas-textMuted hidden sm:inline">
                / v0.1.0-dev
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 text-xs font-mono">
              <span className="text-canvas-textMuted hidden md:inline">API Gateway:</span>
              {health ? (
                <StatusBadge status={health.status} />
              ) : (
                <span className="text-[11px] font-mono text-zinc-500">Checking...</span>
              )}
            </div>

            <button
              onClick={onRefresh}
              disabled={loading}
              title="Ping Backend API"
              className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded text-xs font-mono text-canvas-textSecondary bg-canvas-elevated hover:bg-zinc-800 border border-canvas-border hover:border-zinc-700 transition-colors disabled:opacity-40"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin text-accent' : ''}`} />
              <span className="hidden sm:inline">Ping</span>
            </button>
          </div>
        </div>

        {/* Compact Navigation Tabs */}
        <div className="flex items-center space-x-1 overflow-x-auto py-1.5 -mb-px border-t border-canvas-borderSubtle text-xs font-mono scrollbar-none">
          <button
            className="px-3 py-1 rounded font-medium text-canvas-textPrimary bg-canvas-elevated border border-canvas-border cursor-default flex items-center space-x-1.5"
          >
            <Activity className="w-3.5 h-3.5 text-accent" />
            <span>Overview & Architecture</span>
          </button>

          <div className="group relative">
            <button
              disabled
              className="px-3 py-1 rounded text-canvas-textMuted hover:text-zinc-400 cursor-not-allowed flex items-center space-x-1"
            >
              <span>Sender</span>
              <span className="text-[10px] text-zinc-600 bg-zinc-900 px-1 rounded border border-zinc-800">Phase 3</span>
            </button>
          </div>

          <div className="group relative">
            <button
              disabled
              className="px-3 py-1 rounded text-canvas-textMuted hover:text-zinc-400 cursor-not-allowed flex items-center space-x-1"
            >
              <span>Receiver</span>
              <span className="text-[10px] text-zinc-600 bg-zinc-900 px-1 rounded border border-zinc-800">Phase 3</span>
            </button>
          </div>

          <div className="group relative">
            <button
              disabled
              className="px-3 py-1 rounded text-canvas-textMuted hover:text-zinc-400 cursor-not-allowed flex items-center space-x-1"
            >
              <span>Steganalysis</span>
              <span className="text-[10px] text-zinc-600 bg-zinc-900 px-1 rounded border border-zinc-800">Phase 8</span>
            </button>
          </div>

          <div className="group relative">
            <button
              disabled
              className="px-3 py-1 rounded text-canvas-textMuted hover:text-zinc-400 cursor-not-allowed flex items-center space-x-1"
            >
              <span>Evaluation Lab</span>
              <span className="text-[10px] text-zinc-600 bg-zinc-900 px-1 rounded border border-zinc-800">Phase 9</span>
            </button>
          </div>

          <div className="group relative">
            <button
              disabled
              className="px-3 py-1 rounded text-canvas-textMuted hover:text-zinc-400 cursor-not-allowed flex items-center space-x-1"
            >
              <span>Methodology & Docs</span>
              <span className="text-[10px] text-zinc-600 bg-zinc-900 px-1 rounded border border-zinc-800">docs/</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
