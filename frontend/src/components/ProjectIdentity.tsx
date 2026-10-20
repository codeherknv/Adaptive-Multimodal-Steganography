import React from 'react';
import { Shield, BookOpen, Layers, CheckCircle2 } from 'lucide-react';

interface ProjectIdentityProps {
  currentPhase: number;
}

export const ProjectIdentity: React.FC<ProjectIdentityProps> = ({ currentPhase }) => {
  return (
    <section className="border border-canvas-border bg-canvas-surface rounded-lg p-6 sm:p-7">
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
        <div className="space-y-3 max-w-3xl">
          <div className="flex items-center space-x-2 text-xs font-mono text-canvas-textMuted">
            <span className="inline-flex items-center px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
              CS Honours Research Prototype
            </span>
            <span>•</span>
            <span className="text-canvas-textMuted">Multimodal Steganography & Steganalysis</span>
          </div>

          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-canvas-textPrimary leading-snug">
            Reliability-Aware Adaptive Multimodal Steganography with Machine-Learning-Based Steganalysis Across Image, Audio and Video
          </h1>

          <p className="text-sm text-canvas-textSecondary leading-relaxed">
            This academic research platform investigates whether an empirically informed adaptive payload allocation policy 
            across heterogeneous carrier media (PNG image, 16-bit PCM WAV audio, and video frames) can systematically optimize the 
            trade-off among payload capacity, media distortion (PSNR/SNR), recovery reliability under channel noise, and 
            statistical undetectability against machine-learning steganalysis baselines.
          </p>
        </div>

        {/* Development Status Summary Box */}
        <div className="shrink-0 w-full md:w-64 border border-canvas-border bg-canvas-elevated rounded-md p-4 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-canvas-border">
            <span className="text-xs font-mono uppercase tracking-wider text-canvas-textMuted">Engineering State</span>
            <span className="inline-flex items-center space-x-1 text-xs font-mono text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Phase {currentPhase} Baseline</span>
            </span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between items-baseline">
              <span className="text-canvas-textMuted font-mono text-[11px]">Primary Carrier:</span>
              <span className="text-canvas-textPrimary font-mono">PNG / WAV / Video</span>
            </div>
            <div className="flex justify-between items-baseline">
              <span className="text-canvas-textMuted font-mono text-[11px]">Cryptography:</span>
              <span className="text-canvas-textPrimary font-mono">AES-256-GCM (Phase 2)</span>
            </div>
            <div className="flex justify-between items-baseline">
              <span className="text-canvas-textMuted font-mono text-[11px]">Active Layer:</span>
              <span className="text-sky-300 font-mono">API & Framework</span>
            </div>
            <div className="flex justify-between items-baseline">
              <span className="text-canvas-textMuted font-mono text-[11px]">Steganalysis:</span>
              <span className="text-zinc-500 font-mono">Staged (Phase 8)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Principles Strip */}
      <div className="mt-6 pt-5 border-t border-canvas-border grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
        <div className="flex items-start space-x-2.5">
          <Shield className="w-4 h-4 text-canvas-textSecondary shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-canvas-textPrimary block">Defense-in-Depth</span>
            <span className="text-canvas-textMuted leading-relaxed">
              Authenticated AES-GCM guarantees confidentiality even if steganalysis detects carrier anomalies.
            </span>
          </div>
        </div>

        <div className="flex items-start space-x-2.5">
          <Layers className="w-4 h-4 text-canvas-textSecondary shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-canvas-textPrimary block">Multimodal Allocation</span>
            <span className="text-canvas-textMuted leading-relaxed">
              Splits ciphertext into authenticated frames distributed across spatial, acoustic, and temporal domains.
            </span>
          </div>
        </div>

        <div className="flex items-start space-x-2.5">
          <BookOpen className="w-4 h-4 text-canvas-textSecondary shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-canvas-textPrimary block">Empirical Hypothesis</span>
            <span className="text-canvas-textMuted leading-relaxed">
              Claims of improved security or capacity are verified only via controlled, reproducible experiments.
            </span>
          </div>
        </div>
      </div>
    </section>
  );
};
