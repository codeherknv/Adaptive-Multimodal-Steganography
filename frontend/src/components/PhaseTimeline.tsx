import React, { useState } from 'react';
import { ChevronDown, ShieldCheck } from 'lucide-react';
import { StatusBadge, StatusType } from './StatusBadge';

interface PhaseItem {
  id: number;
  title: string;
  scope: string;
  acceptanceCriteria: string;
  status: StatusType;
  verificationEvidence?: string;
}

const PHASES_DATA: PhaseItem[] = [
  {
    id: 0,
    title: "Environment & Toolchain Inspection",
    scope: "Verify Python 3.13, Node 22, npm 10, Git CLI, and port availability on Windows workspace.",
    acceptanceCriteria: "Tool versions detected and documented; working tree clean; ports 8000 and 5173 verified available.",
    status: "completed",
    verificationEvidence: "Python 3.13.2, pip 24.3.1, Node v22.16.0, Git 2.51.0 confirmed via shell inspection."
  },
  {
    id: 1,
    title: "Monorepo Scaffolding & API Baseline",
    scope: "Initialize FastAPI backend, React/Vite/TS frontend, dependencies, .gitignore, and health/status endpoints.",
    acceptanceCriteria: "Both servers start independently; API reverse proxy operational; pytest suite passing with zero failures.",
    status: "completed",
    verificationEvidence: "Pytest passing (3 tests); Vite build verified (0 errors); /api/health and /api/status returning 200 OK."
  },
  {
    id: 2,
    title: "AES-256-GCM Encryption & Binary Payload Codec",
    scope: "Implement authenticated encryption with fresh 96-bit nonces, 128-bit auth tags, and versioned binary framing.",
    acceptanceCriteria: "Tampering or truncation causes authenticated rejection; chunk metadata validated; unit tests pass.",
    status: "completed",
    verificationEvidence: "47 automated tests passing; AES-256-GCM round trips, PBKDF2, and binary ASTG framing verified."
  },
  {
    id: 3,
    title: "Spatial LSB Image Steganography",
    scope: "Implement lossless PNG least-significant-bit embedding/extraction with capacity checks and distortion metrics.",
    acceptanceCriteria: "100% exact bit recovery on clean PNGs; PSNR/MSE distortion calculated; capacity limits enforced.",
    status: "completed",
    verificationEvidence: "65 automated tests passing; PNG spatial LSB round trips, PSTG 14-byte framing, CRC32 checks, MSE/PSNR/SSIM metrics verified."
  },
  {
    id: 4,
    title: "PCM WAV Audio Steganography",
    scope: "Implement 16-bit & 8-bit PCM WAV audio embedding and extraction while preserving RIFF/WAV headers and measuring SNR/MSE distortion.",
    acceptanceCriteria: "Exact extraction verified; SNR and normalized MSE measured; sample rate, channels, bit depth, and duration preserved; WSTG framing validated.",
    status: "completed",
    verificationEvidence: "90 automated tests passing; WAV sample LSB round trips (mono & stereo), WSTG 14-byte framing, CRC32 checks, SNR/MSE metrics verified."
  },
  {
    id: 5,
    title: "Frame-Based Video Steganography",
    scope: "Lossless video container processing using OpenCV with multi-frame spatial LSB embedding, VSTG framing, and average frame MSE/PSNR metrics.",
    acceptanceCriteria: "Exact extraction verified; dimensions and frame rate preserved; lossless codec availability checked; VSTG framing validated.",
    status: "completed",
    verificationEvidence: "110 automated tests passing; multi-frame spatial LSB round trips, VSTG 14-byte framing, CRC32 checks, average frame MSE & PSNR metrics verified."
  },
  {
    id: 6,
    title: "Unified Multimodal Allocation & Recovery",
    scope: "Implement carrier profiling (Laplacian, RMS, motion variance), fixed baseline and adaptive feature-weighted allocation, and unified triad bundle embedding/extraction.",
    acceptanceCriteria: "Multi-carrier partitioning accounts for framing overheads; bit-exact recovery across Image, Audio, and Video; automated tests pass.",
    status: "completed",
    verificationEvidence: "136 automated tests passing; profiling metrics, fixed & adaptive allocation algorithms, ZIP bundle packaging, and E2E API round-trips verified."
  },
  {
    id: 7,
    title: "Steganalysis Dataset Pipeline & ML Baselines",
    scope: "Extract first- and higher-order statistical features from cover/stego media, enforce zero-leakage source partitioning, and train scikit-learn classifiers.",
    acceptanceCriteria: "Zero-leakage source partitioning; Confusion matrix, ROC-AUC, precision, recall, and F1 measured across matched conditions.",
    status: "completed",
    verificationEvidence: "156 automated tests passing; 10 image, 8 audio, 7 video statistical features, GroupShuffleSplit zero-leakage training, and model evaluation verified."
  },
  {
    id: 8,
    title: "Research Validation & Comparative Evaluation",
    scope: "Paired comparative trials comparing Fixed Baseline vs. Adaptive Feature allocation on identical carrier triads and payloads with 95% confidence intervals and steganalysis profiling.",
    acceptanceCriteria: "Fair paired inputs guaranteed; 100% authenticated recovery verified; Student's t-test and paired deltas computed; non-silent failure tracking.",
    status: "completed",
    verificationEvidence: "167 automated tests passing; 24 paired trials, Image PSNR +3.06 dB gain (p=0.0004), matched plots and JSON exports verified."
  },
  {
    id: 9,
    title: "Quality, Robustness & Runtime Benchmarking",
    scope: "Implement automated benchmark laboratory measuring PSNR, SNR, BER, recovery reliability, and processing time.",
    acceptanceCriteria: "Channel transformation experiments (recompression/noise); reproducible metrics recorded.",
    status: "staged",
  },
  {
    id: 10,
    title: "Empirical Adaptive Allocation Policy",
    scope: "Develop an informed allocation algorithm that balances capacity, distortion tolerance, and detectability risk.",
    acceptanceCriteria: "Clear target objective function; transparent rule-based policy compared against fixed baseline.",
    status: "staged",
  },
  {
    id: 11,
    title: "Comparative Allocation & Ablation Analysis",
    scope: "Execute matched-condition benchmarks comparing fixed vs. adaptive allocation across varied payload densities.",
    acceptanceCriteria: "Ablation of feature sets; honest reporting of trade-offs, gains, and negative results.",
    status: "staged",
  },
  {
    id: 12,
    title: "Comprehensive Evaluation Dashboard & CSV Export",
    scope: "Interactive visualization in Recharts for ROC curves, distortion vs capacity curves, and CSV data export.",
    acceptanceCriteria: "All charts derived from real stored experiment records; export files verified.",
    status: "staged",
  },
  {
    id: 13,
    title: "Security Review, Final Research Report & Defense",
    scope: "Full automated test suite regression, vulnerability analysis, architecture documentation, and presentation materials.",
    acceptanceCriteria: "Zero unresolved test failures; verified literature citations; structured thesis/defense slides.",
    status: "staged",
  }
];

export const PhaseTimeline: React.FC = () => {
  const [showAllPhases, setShowAllPhases] = useState<boolean>(false);

  // By default, display through Phase 7 to maintain compact view, with toggle to inspect full curriculum
  const displayedPhases = showAllPhases ? PHASES_DATA : PHASES_DATA.slice(0, 8);

  return (
    <section className="border border-canvas-border bg-canvas-surface rounded-lg p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-canvas-border">
        <div>
          <h2 className="text-sm font-semibold text-canvas-textPrimary tracking-tight">
            Engineering Roadmap & Phase Execution
          </h2>
          <p className="text-xs text-canvas-textMuted">
            Sequential 14-phase development roadmap. Progress is recorded through verifiable automated tests.
          </p>
        </div>
        <button
          onClick={() => setShowAllPhases(!showAllPhases)}
          className="inline-flex items-center space-x-1.5 text-xs font-mono text-canvas-textSecondary hover:text-canvas-textPrimary bg-canvas-elevated hover:bg-zinc-800 px-2.5 py-1 rounded border border-canvas-border transition-colors self-start sm:self-auto"
        >
          <span>{showAllPhases ? "Collapse Staged Phases" : `Show All 14 Phases (${PHASES_DATA.length})`}</span>
          <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showAllPhases ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* Structured Vertical Progress List */}
      <div className="relative border-l border-zinc-800 ml-3.5 pl-5 space-y-4 py-1">
        {displayedPhases.map((phase) => {
          const isCompleted = phase.status === 'completed';
          const isCurrent = phase.status === 'current';

          return (
            <div key={phase.id} className="relative group">
              {/* Dot on vertical line */}
              <div 
                className={`absolute -left-[27px] top-1.5 w-3.5 h-3.5 rounded-full flex items-center justify-center border ${
                  isCompleted 
                    ? 'bg-emerald-950 border-emerald-500 text-emerald-400' 
                    : isCurrent 
                      ? 'bg-sky-950 border-sky-400 text-sky-400 ring-2 ring-sky-900/40' 
                      : 'bg-zinc-900 border-zinc-700 text-zinc-600'
                }`}
              >
                {isCompleted && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />}
                {isCurrent && <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />}
              </div>

              {/* Phase Card */}
              <div 
                className={`border rounded-md p-3.5 transition-colors ${
                  isCurrent 
                    ? 'border-sky-900/60 bg-sky-950/10' 
                    : isCompleted 
                      ? 'border-canvas-border bg-canvas-elevated/40' 
                      : 'border-canvas-borderSubtle bg-canvas-elevated/20 opacity-80'
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-xs font-semibold text-canvas-textPrimary">
                      Phase {phase.id}: {phase.title}
                    </span>
                  </div>
                  <div>
                    <StatusBadge 
                      status={phase.status} 
                      label={
                        isCompleted 
                          ? "Completed & Verified" 
                          : isCurrent 
                            ? "Next Implementation Target" 
                            : "Staged"
                      }
                    />
                  </div>
                </div>

                <p className="mt-1.5 text-xs text-canvas-textSecondary leading-relaxed">
                  {phase.scope}
                </p>

                {phase.verificationEvidence && (
                  <div className="mt-2.5 pt-2 border-t border-canvas-borderSubtle flex items-start space-x-2 text-[11px] font-mono text-emerald-400/90">
                    <ShieldCheck className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    <span>Evidence: {phase.verificationEvidence}</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {!showAllPhases && (
        <div className="pt-1 text-center">
          <button
            onClick={() => setShowAllPhases(true)}
            className="text-xs font-mono text-canvas-textMuted hover:text-canvas-textSecondary transition-colors"
          >
            + 9 additional staged phases in sequential roadmap (Click to expand)
          </button>
        </div>
      )}
    </section>
  );
};
