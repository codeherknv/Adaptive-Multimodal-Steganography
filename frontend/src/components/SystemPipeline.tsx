import React from 'react';
import { 
  Key, 
  Lock, 
  Split, 
  Image, 
  Music, 
  Video, 
  Unlock, 
  BarChart2, 
  Info 
} from 'lucide-react';

export const SystemPipeline: React.FC = () => {
  return (
    <section className="border border-canvas-border bg-canvas-surface rounded-lg p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-canvas-border">
        <div>
          <h2 className="text-sm font-semibold text-canvas-textPrimary tracking-tight">
            System Architecture & Experimental Pipeline
          </h2>
          <p className="text-xs text-canvas-textMuted">
            End-to-end data flow specification: from secret input to authenticated recovery and steganalytic evaluation.
          </p>
        </div>
        <div className="flex items-center space-x-3 text-[11px] font-mono">
          <span className="flex items-center space-x-1 text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span>Implemented (API / Monorepo)</span>
          </span>
          <span className="flex items-center space-x-1 text-zinc-500">
            <span className="w-2 h-2 rounded-full bg-zinc-600" />
            <span>Planned Research Module</span>
          </span>
        </div>
      </div>

      {/* Pipeline Flow Grid */}
      <div className="grid grid-cols-1 md:grid-cols-6 gap-3 relative">
        {/* Step 1: Input */}
        <div className="border border-dashed border-canvas-border bg-canvas-elevated/40 rounded-md p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">Step 1</span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-900 text-zinc-500 border border-zinc-800">Planned</span>
          </div>
          <div className="my-2.5">
            <div className="flex items-center space-x-1.5 text-zinc-300 font-medium text-xs">
              <Key className="w-3.5 h-3.5 text-zinc-400" />
              <span>Input & Key</span>
            </div>
            <p className="text-[11px] text-zinc-500 mt-1">
              Secret plaintext & local key derivation.
            </p>
          </div>
          <div className="text-[10px] font-mono text-zinc-500 pt-2 border-t border-canvas-borderSubtle">
            Phase 2 target
          </div>
        </div>

        {/* Step 2: Cryptography */}
        <div className="border border-dashed border-canvas-border bg-canvas-elevated/40 rounded-md p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">Step 2</span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-900 text-zinc-500 border border-zinc-800">Planned</span>
          </div>
          <div className="my-2.5">
            <div className="flex items-center space-x-1.5 text-zinc-300 font-medium text-xs">
              <Lock className="w-3.5 h-3.5 text-zinc-400" />
              <span>AES-256-GCM</span>
            </div>
            <p className="text-[11px] text-zinc-500 mt-1">
              Fresh nonce, ciphertext & 128-bit auth tag.
            </p>
          </div>
          <div className="text-[10px] font-mono text-zinc-500 pt-2 border-t border-canvas-borderSubtle">
            Phase 2 target
          </div>
        </div>

        {/* Step 3: Allocation */}
        <div className="border border-dashed border-canvas-border bg-canvas-elevated/40 rounded-md p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">Step 3</span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-900 text-zinc-500 border border-zinc-800">Planned</span>
          </div>
          <div className="my-2.5">
            <div className="flex items-center space-x-1.5 text-zinc-300 font-medium text-xs">
              <Split className="w-3.5 h-3.5 text-zinc-400" />
              <span>Allocation Policy</span>
            </div>
            <p className="text-[11px] text-zinc-500 mt-1">
              Fixed split vs. adaptive ML allocation.
            </p>
          </div>
          <div className="text-[10px] font-mono text-zinc-500 pt-2 border-t border-canvas-borderSubtle">
            Phase 7 & 10 target
          </div>
        </div>

        {/* Step 4: Multimodal Embedding */}
        <div className="border border-dashed border-canvas-border bg-canvas-elevated/40 rounded-md p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">Step 4</span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-900 text-zinc-500 border border-zinc-800">Planned</span>
          </div>
          <div className="my-2.5">
            <div className="text-zinc-300 font-medium text-xs mb-1">
              <span>Carrier Embedding</span>
            </div>
            <div className="flex items-center space-x-2 text-zinc-400 text-[11px]">
              <span className="flex items-center space-x-1" title="PNG LSB">
                <Image className="w-3 h-3" />
                <span>Img</span>
              </span>
              <span>•</span>
              <span className="flex items-center space-x-1" title="WAV PCM">
                <Music className="w-3 h-3" />
                <span>Aud</span>
              </span>
              <span>•</span>
              <span className="flex items-center space-x-1" title="Video frames">
                <Video className="w-3 h-3" />
                <span>Vid</span>
              </span>
            </div>
          </div>
          <div className="text-[10px] font-mono text-zinc-500 pt-2 border-t border-canvas-borderSubtle">
            Phases 3, 5, 6 target
          </div>
        </div>

        {/* Step 5: Recovery */}
        <div className="border border-dashed border-canvas-border bg-canvas-elevated/40 rounded-md p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">Step 5</span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-900 text-zinc-500 border border-zinc-800">Planned</span>
          </div>
          <div className="my-2.5">
            <div className="flex items-center space-x-1.5 text-zinc-300 font-medium text-xs">
              <Unlock className="w-3.5 h-3.5 text-zinc-400" />
              <span>Extraction & Auth</span>
            </div>
            <p className="text-[11px] text-zinc-500 mt-1">
              Reassembly & authenticated verification.
            </p>
          </div>
          <div className="text-[10px] font-mono text-zinc-500 pt-2 border-t border-canvas-borderSubtle">
            Phases 4 & 7 target
          </div>
        </div>

        {/* Step 6: Steganalysis & Evaluation */}
        <div className="border border-dashed border-canvas-border bg-canvas-elevated/40 rounded-md p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">Step 6</span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-900 text-zinc-500 border border-zinc-800">Planned</span>
          </div>
          <div className="my-2.5">
            <div className="flex items-center space-x-1.5 text-zinc-300 font-medium text-xs">
              <BarChart2 className="w-3.5 h-3.5 text-zinc-400" />
              <span>Steganalysis & Lab</span>
            </div>
            <p className="text-[11px] text-zinc-500 mt-1">
              Feature extraction, ML baseline, PSNR/SNR.
            </p>
          </div>
          <div className="text-[10px] font-mono text-zinc-500 pt-2 border-t border-canvas-borderSubtle">
            Phases 8 & 9 target
          </div>
        </div>
      </div>

      {/* Architecture Disclaimer */}
      <div className="flex items-start space-x-2 text-xs text-canvas-textMuted bg-canvas-elevated p-3 rounded border border-canvas-borderSubtle">
        <Info className="w-4 h-4 text-canvas-textSecondary shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          <strong className="text-canvas-textSecondary">Architectural Note:</strong> The pipeline above outlines the planned end-to-end data flow specified in the project roadmap. Currently, <span className="text-emerald-400 font-mono">Phase 1</span> (Monorepo foundation, FastAPI REST gateway, and testing harness) is verified and running. Core cryptography, steganographic codecs, and machine learning components will be activated sequentially in subsequent phases.
        </p>
      </div>
    </section>
  );
};
