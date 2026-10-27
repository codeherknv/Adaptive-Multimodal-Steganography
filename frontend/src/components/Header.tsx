import React from 'react';
import { Terminal, ArrowUpRight, ArrowDownLeft, Layers } from 'lucide-react';

export type TabType = 'triad' | 'sender' | 'receiver';

interface HeaderProps {
  activeTab: TabType;
  onSelectTab: (tab: TabType) => void;
}

export const Header: React.FC<HeaderProps> = ({ 
  activeTab, 
  onSelectTab 
}) => {
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
              <span className="font-mono text-sm font-semibold tracking-wider text-canvas-textPrimary uppercase">
                Adaptive Steganography Workbench
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-2 text-xs font-mono text-canvas-textMuted hidden sm:flex">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>Multimodal Research Platform</span>
          </div>
        </div>

        {/* Clean Navigation Tabs */}
        <div className="flex items-center space-x-1 overflow-x-auto py-1.5 -mb-px border-t border-canvas-borderSubtle text-xs font-mono scrollbar-none">
          <button
            onClick={() => onSelectTab('triad')}
            className={`px-3 py-1.5 rounded font-medium transition-colors flex items-center space-x-1.5 ${
              activeTab === 'triad'
                ? 'text-canvas-textPrimary bg-canvas-elevated border border-canvas-border shadow-sm'
                : 'text-canvas-textMuted hover:text-canvas-textSecondary hover:bg-zinc-900/40 border border-transparent'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-accent" />
            <span>Multimodal Triad</span>
          </button>

          <button
            onClick={() => onSelectTab('sender')}
            className={`px-3 py-1.5 rounded font-medium transition-colors flex items-center space-x-1.5 ${
              activeTab === 'sender'
                ? 'text-canvas-textPrimary bg-canvas-elevated border border-canvas-border shadow-sm'
                : 'text-canvas-textMuted hover:text-canvas-textSecondary hover:bg-zinc-900/40 border border-transparent'
            }`}
          >
            <ArrowUpRight className="w-3.5 h-3.5 text-zinc-400" />
            <span>Sender (Embed)</span>
          </button>

          <button
            onClick={() => onSelectTab('receiver')}
            className={`px-3 py-1.5 rounded font-medium transition-colors flex items-center space-x-1.5 ${
              activeTab === 'receiver'
                ? 'text-canvas-textPrimary bg-canvas-elevated border border-canvas-border shadow-sm'
                : 'text-canvas-textMuted hover:text-canvas-textSecondary hover:bg-zinc-900/40 border border-transparent'
            }`}
          >
            <ArrowDownLeft className="w-3.5 h-3.5 text-zinc-400" />
            <span>Receiver (Extract)</span>
          </button>
        </div>
      </div>
    </header>
  );
};
