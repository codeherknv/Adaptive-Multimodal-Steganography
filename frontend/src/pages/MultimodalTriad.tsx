import React, { useState } from 'react';
import { 
  Key, 
  Download, 
  CheckCircle2, 
  AlertCircle, 
  Lock, 
  Unlock, 
  BarChart3, 
  Cpu, 
  Image as ImageIcon, 
  Music, 
  Video as VideoIcon, 
  Copy, 
  Check, 
  RefreshCw,
  Info,
  Archive
} from 'lucide-react';
import { 
  analyzeMultimodalTriad, 
  embedMultimodal, 
  extractMultimodal 
} from '../api/client';
import { 
  MultimodalAnalyzeResponse, 
  MultimodalEmbedResponse, 
  MultimodalExtractResponse 
} from '../api/types';

export const MultimodalTriad: React.FC = () => {
  const [activeWorkflow, setActiveWorkflow] = useState<'embed' | 'extract'>('embed');

  // Embed Mode State
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [strategy, setStrategy] = useState<'adaptive' | 'fixed'>('adaptive');
  
  // Profiling State
  const [profilingLoading, setProfilingLoading] = useState<boolean>(false);
  const [profileData, setProfileData] = useState<MultimodalAnalyzeResponse | null>(null);
  const [profilingError, setProfilingError] = useState<string | null>(null);

  // Embedding State
  const [embedLoading, setEmbedLoading] = useState<boolean>(false);
  const [embedError, setEmbedError] = useState<string | null>(null);
  const [embedResult, setEmbedResult] = useState<MultimodalEmbedResponse | null>(null);

  // Extract Mode State
  const [extractMode, setExtractMode] = useState<'zip' | 'individual'>('zip');
  const [zipBundleFile, setZipBundleFile] = useState<File | null>(null);
  const [extractImageFile, setExtractImageFile] = useState<File | null>(null);
  const [extractAudioFile, setExtractAudioFile] = useState<File | null>(null);
  const [extractVideoFile, setExtractVideoFile] = useState<File | null>(null);
  const [extractPassword, setExtractPassword] = useState<string>('');
  const [extractKey, setExtractKey] = useState<string>('');
  const [extractSalt, setExtractSalt] = useState<string>('');
  const [extractLoading, setExtractLoading] = useState<boolean>(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [extractResult, setExtractResult] = useState<MultimodalExtractResponse | null>(null);

  // Utility Copy State
  const [copiedKey, setCopiedKey] = useState<boolean>(false);
  const [copiedPlaintext, setCopiedPlaintext] = useState<boolean>(false);

  // -------------------------------------------------------------
  // Handlers: Profiling
  // -------------------------------------------------------------
  const handleProfileCarriers = async () => {
    if (!imageFile || !audioFile || !videoFile) {
      setProfilingError('Please upload all three cover carriers (PNG Image, WAV Audio, and Video) to profile.');
      return;
    }

    setProfilingLoading(true);
    setProfilingError(null);
    try {
      const formData = new FormData();
      formData.append('image', imageFile);
      formData.append('audio', audioFile);
      formData.append('video', videoFile);
      if (message.trim().length > 0) {
        // Approximate envelope size: plaintext bytes + 30 bytes AES-GCM envelope
        const estLen = new TextEncoder().encode(message).length + 30;
        formData.append('payload_length', estLen.toString());
        formData.append('strategy', strategy);
      }
      const data = await analyzeMultimodalTriad(formData);
      setProfileData(data);
    } catch (err: any) {
      setProfilingError(err.response?.data?.detail || err.message || 'Carrier profiling failed.');
    } finally {
      setProfilingLoading(false);
    }
  };

  // -------------------------------------------------------------
  // Handlers: Embedding
  // -------------------------------------------------------------
  const handleEmbedMultimodal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!imageFile || !audioFile || !videoFile) {
      setEmbedError('Please provide all three cover carrier files.');
      return;
    }
    if (!message.trim()) {
      setEmbedError('Secret message cannot be empty.');
      return;
    }

    setEmbedLoading(true);
    setEmbedError(null);
    setEmbedResult(null);

    try {
      const formData = new FormData();
      formData.append('image', imageFile);
      formData.append('audio', audioFile);
      formData.append('video', videoFile);
      formData.append('message', message);
      formData.append('strategy', strategy);
      if (password.trim()) {
        formData.append('password', password);
      }
      formData.append('encoding', 'base64');

      const data = await embedMultimodal(formData);
      setEmbedResult(data);
    } catch (err: any) {
      setEmbedError(err.response?.data?.detail || err.message || 'Multimodal embedding failed.');
    } finally {
      setEmbedLoading(false);
    }
  };

  // -------------------------------------------------------------
  // Handlers: Extraction
  // -------------------------------------------------------------
  const handleExtractMultimodal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (extractMode === 'zip' && !zipBundleFile) {
      setExtractError('Please upload the stego carrier ZIP bundle.');
      return;
    }
    if (extractMode === 'individual' && (!extractImageFile || !extractAudioFile || !extractVideoFile)) {
      setExtractError('Please upload all three stego carrier files.');
      return;
    }
    if (!extractPassword.trim() && !extractKey.trim()) {
      setExtractError('Provide either the secret passphrase or the direct 32-byte AES key.');
      return;
    }

    setExtractLoading(true);
    setExtractError(null);
    setExtractResult(null);

    try {
      const formData = new FormData();
      if (extractMode === 'zip' && zipBundleFile) {
        formData.append('bundle_zip', zipBundleFile);
      } else {
        if (extractImageFile) formData.append('image', extractImageFile);
        if (extractAudioFile) formData.append('audio', extractAudioFile);
        if (extractVideoFile) formData.append('video', extractVideoFile);
      }

      if (extractKey.trim()) {
        formData.append('key', extractKey.trim());
      } else if (extractPassword.trim()) {
        formData.append('password', extractPassword.trim());
        if (extractSalt.trim()) {
          formData.append('salt', extractSalt.trim());
        }
      }
      formData.append('encoding', 'base64');

      const data = await extractMultimodal(formData);
      setExtractResult(data);
    } catch (err: any) {
      setExtractError(err.response?.data?.detail || err.message || 'Multimodal extraction failed.');
    } finally {
      setExtractLoading(false);
    }
  };

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* Header Banner */}
      <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-accent/10 border border-accent/30 text-accent font-semibold uppercase tracking-wider">
                Phase 6 Engine
              </span>
              <span className="text-xs font-mono text-canvas-textMuted">
                Multimodal Triad Allocation & Orchestration
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-canvas-textPrimary">
              Multimodal Triad Workbench
            </h1>
            <p className="text-xs sm:text-sm text-canvas-textSecondary max-w-3xl leading-relaxed">
              Partition a cryptographically encrypted AES-256-GCM payload across heterogeneous carriers
              (PNG Image, WAV Audio, FFV1 Video) using deterministic fixed or entropy-weighted adaptive strategies.
            </p>
          </div>

          {/* Workflow Toggle */}
          <div className="inline-flex rounded-lg border border-canvas-border bg-canvas-elevated p-1 self-start sm:self-auto font-mono text-xs">
            <button
              onClick={() => setActiveWorkflow('embed')}
              className={`px-3 py-1.5 rounded transition-colors flex items-center space-x-1.5 ${
                activeWorkflow === 'embed'
                  ? 'bg-zinc-800 text-canvas-textPrimary shadow-sm border border-zinc-700/60'
                  : 'text-canvas-textMuted hover:text-canvas-textSecondary'
              }`}
            >
              <Lock className="w-3.5 h-3.5 text-accent" />
              <span>Embed & Bundle</span>
            </button>
            <button
              onClick={() => setActiveWorkflow('extract')}
              className={`px-3 py-1.5 rounded transition-colors flex items-center space-x-1.5 ${
                activeWorkflow === 'extract'
                  ? 'bg-zinc-800 text-canvas-textPrimary shadow-sm border border-zinc-700/60'
                  : 'text-canvas-textMuted hover:text-canvas-textSecondary'
              }`}
            >
              <Unlock className="w-3.5 h-3.5 text-emerald-400" />
              <span>Extract & Reassemble</span>
            </button>
          </div>
        </div>
      </div>

      {/* ========================================================= */}
      {/* WORKFLOW: EMBED & BUNDLE                                  */}
      {/* ========================================================= */}
      {activeWorkflow === 'embed' && (
        <div className="space-y-6">
          <form onSubmit={handleEmbedMultimodal} className="space-y-6">
            {/* Step 1: Upload Carrier Triad */}
            <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="w-6 h-6 rounded-full bg-accent/15 border border-accent/40 text-accent font-mono text-xs flex items-center justify-center font-bold">
                    1
                  </span>
                  <h2 className="text-sm font-semibold text-canvas-textPrimary font-mono uppercase tracking-wider">
                    Select Cover Carrier Triad
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={handleProfileCarriers}
                  disabled={!imageFile || !audioFile || !videoFile || profilingLoading}
                  className="inline-flex items-center space-x-1.5 px-3 py-1 rounded text-xs font-mono bg-canvas-elevated hover:bg-zinc-800 border border-canvas-border text-canvas-textSecondary disabled:opacity-40 transition-colors"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${profilingLoading ? 'animate-spin text-accent' : ''}`} />
                  <span>Profile Carriers</span>
                </button>
              </div>

              {profilingError && (
                <div className="rounded border border-red-800/40 bg-red-950/20 p-3 text-xs font-mono text-red-300 flex items-start space-x-2">
                  <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                  <span>{profilingError}</span>
                </div>
              )}

              {/* Triad Upload Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* 1. Image Upload */}
                <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated/40 p-4 space-y-3">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="flex items-center space-x-1.5 text-zinc-300 font-semibold">
                      <ImageIcon className="w-4 h-4 text-accent" />
                      <span>PNG Image</span>
                    </span>
                    <span className="text-[10px] text-zinc-500 uppercase">PSTG Frame</span>
                  </div>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={(e) => setImageFile(e.target.files?.[0] || null)}
                    className="block w-full text-xs font-mono text-zinc-400 file:mr-2 file:py-1 file:px-2.5 file:rounded file:border-0 file:text-[11px] file:font-mono file:bg-zinc-800 file:text-zinc-200 hover:file:bg-zinc-700 cursor-pointer"
                  />
                  {imageFile && (
                    <div className="text-[11px] font-mono text-zinc-400 space-y-0.5 border-t border-canvas-borderSubtle pt-2">
                      <p className="truncate font-semibold text-zinc-300">{imageFile.name}</p>
                      <p>{(imageFile.size / 1024).toFixed(1)} KB</p>
                    </div>
                  )}
                </div>

                {/* 2. Audio Upload */}
                <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated/40 p-4 space-y-3">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="flex items-center space-x-1.5 text-zinc-300 font-semibold">
                      <Music className="w-4 h-4 text-emerald-400" />
                      <span>WAV Audio</span>
                    </span>
                    <span className="text-[10px] text-zinc-500 uppercase">WSTG Frame</span>
                  </div>
                  <input
                    type="file"
                    accept="audio/wav,audio/x-wav"
                    onChange={(e) => setAudioFile(e.target.files?.[0] || null)}
                    className="block w-full text-xs font-mono text-zinc-400 file:mr-2 file:py-1 file:px-2.5 file:rounded file:border-0 file:text-[11px] file:font-mono file:bg-zinc-800 file:text-zinc-200 hover:file:bg-zinc-700 cursor-pointer"
                  />
                  {audioFile && (
                    <div className="text-[11px] font-mono text-zinc-400 space-y-0.5 border-t border-canvas-borderSubtle pt-2">
                      <p className="truncate font-semibold text-zinc-300">{audioFile.name}</p>
                      <p>{(audioFile.size / 1024).toFixed(1)} KB</p>
                    </div>
                  )}
                </div>

                {/* 3. Video Upload */}
                <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated/40 p-4 space-y-3">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="flex items-center space-x-1.5 text-zinc-300 font-semibold">
                      <VideoIcon className="w-4 h-4 text-purple-400" />
                      <span>Lossless Video</span>
                    </span>
                    <span className="text-[10px] text-zinc-500 uppercase">VSTG Frame</span>
                  </div>
                  <input
                    type="file"
                    accept="video/avi,video/x-msvideo,video/mp4,video/mkv"
                    onChange={(e) => setVideoFile(e.target.files?.[0] || null)}
                    className="block w-full text-xs font-mono text-zinc-400 file:mr-2 file:py-1 file:px-2.5 file:rounded file:border-0 file:text-[11px] file:font-mono file:bg-zinc-800 file:text-zinc-200 hover:file:bg-zinc-700 cursor-pointer"
                  />
                  {videoFile && (
                    <div className="text-[11px] font-mono text-zinc-400 space-y-0.5 border-t border-canvas-borderSubtle pt-2">
                      <p className="truncate font-semibold text-zinc-300">{videoFile.name}</p>
                      <p>{(videoFile.size / (1024 * 1024)).toFixed(2)} MB</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Profiling Results Cards (if profiled) */}
              {profileData && (
                <div className="mt-4 pt-4 border-t border-canvas-borderSubtle space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs font-mono gap-2">
                    <span className="text-zinc-300 font-semibold flex items-center space-x-1.5">
                      <BarChart3 className="w-3.5 h-3.5 text-accent" />
                      <span>Carrier Complexity Profiles & Usable Capacities</span>
                    </span>
                    <span className="text-accent bg-accent/10 px-2 py-0.5 rounded border border-accent/20">
                      Total Net Usable: {profileData.total_usable_capacity_bytes.toLocaleString()} bytes
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-xs">
                    {/* Image Profile Card */}
                    <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 space-y-1.5">
                      <div className="flex justify-between items-center text-zinc-400">
                        <span className="font-semibold text-zinc-200">Image Carrier</span>
                        <span className="text-accent">{profileData.image.width}x{profileData.image.height}</span>
                      </div>
                      <div className="text-[11px] space-y-1 text-zinc-400">
                        <div className="flex justify-between">
                          <span>Laplacian Var:</span>
                          <span className="text-zinc-200 font-semibold">{profileData.image.laplacian_variance}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Complexity Score:</span>
                          <span className="text-zinc-200 font-semibold">{profileData.image.complexity_score}</span>
                        </div>
                        <div className="flex justify-between border-t border-zinc-800/80 pt-1">
                          <span>Max Usable:</span>
                          <span className="text-zinc-200 font-bold">{profileData.image.max_usable_payload_bytes.toLocaleString()} B</span>
                        </div>
                      </div>
                    </div>

                    {/* Audio Profile Card */}
                    <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 space-y-1.5">
                      <div className="flex justify-between items-center text-zinc-400">
                        <span className="font-semibold text-zinc-200">Audio Carrier</span>
                        <span className="text-emerald-400">{profileData.audio.channel_layout} {profileData.audio.sample_rate}Hz</span>
                      </div>
                      <div className="text-[11px] space-y-1 text-zinc-400">
                        <div className="flex justify-between">
                          <span>RMS Energy:</span>
                          <span className="text-zinc-200 font-semibold">{profileData.audio.rms_energy}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Complexity Score:</span>
                          <span className="text-zinc-200 font-semibold">{profileData.audio.complexity_score}</span>
                        </div>
                        <div className="flex justify-between border-t border-zinc-800/80 pt-1">
                          <span>Max Usable:</span>
                          <span className="text-zinc-200 font-bold">{profileData.audio.max_usable_payload_bytes.toLocaleString()} B</span>
                        </div>
                      </div>
                    </div>

                    {/* Video Profile Card */}
                    <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 space-y-1.5">
                      <div className="flex justify-between items-center text-zinc-400">
                        <span className="font-semibold text-zinc-200">Video Carrier</span>
                        <span className="text-purple-400">{profileData.video.num_frames} frames @ {profileData.video.fps}fps</span>
                      </div>
                      <div className="text-[11px] space-y-1 text-zinc-400">
                        <div className="flex justify-between">
                          <span>Frame Diff Var:</span>
                          <span className="text-zinc-200 font-semibold">{profileData.video.frame_diff_variance}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Complexity Score:</span>
                          <span className="text-zinc-200 font-semibold">{profileData.video.complexity_score}</span>
                        </div>
                        <div className="flex justify-between border-t border-zinc-800/80 pt-1">
                          <span>Max Usable:</span>
                          <span className="text-zinc-200 font-bold">{profileData.video.max_usable_payload_bytes.toLocaleString()} B</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Scientific Warning Notice */}
                  <div className="rounded border border-canvas-borderSubtle bg-zinc-900/60 p-2.5 text-[11px] font-mono text-zinc-400 flex items-start space-x-2">
                    <Info className="w-3.5 h-3.5 text-accent mt-0.5 flex-shrink-0" />
                    <span>
                      Scientific Note: Complexity scores reflect empirical spatial/temporal variance (HVS/HAS perceptual masking proxies).
                      They serve as heuristic allocation weights, not proof of undetectability against ML steganalysis classifiers.
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Step 2: Configure Payload & Allocation Strategy */}
            <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-4">
              <div className="flex items-center space-x-2">
                <span className="w-6 h-6 rounded-full bg-accent/15 border border-accent/40 text-accent font-mono text-xs flex items-center justify-center font-bold">
                  2
                </span>
                <h2 className="text-sm font-semibold text-canvas-textPrimary font-mono uppercase tracking-wider">
                  Secret Message & Allocation Strategy
                </h2>
              </div>

              {/* Message Input */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center text-xs font-mono">
                  <label htmlFor="multimodal-msg" className="text-zinc-300 font-medium">
                    Plaintext Message to Conceal
                  </label>
                  <span className="text-zinc-500">{message.length} characters</span>
                </div>
                <textarea
                  id="multimodal-msg"
                  rows={4}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Enter classified or sensitive message to partition across Image, Audio, and Video carriers..."
                  className="w-full rounded border border-canvas-border bg-canvas-elevated/70 px-3 py-2 text-xs font-mono text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-accent"
                />
              </div>

              {/* Password & Strategy Selection */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Strategy Selector */}
                <div className="space-y-1.5">
                  <label className="text-xs font-mono text-zinc-300 font-medium block">
                    Allocation Strategy
                  </label>
                  <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                    <button
                      type="button"
                      onClick={() => setStrategy('adaptive')}
                      className={`p-2.5 rounded border text-left transition-colors ${
                        strategy === 'adaptive'
                          ? 'border-accent bg-accent/10 text-zinc-200 font-semibold shadow-sm'
                          : 'border-canvas-borderSubtle bg-canvas-elevated/60 text-zinc-400 hover:text-zinc-300'
                      }`}
                    >
                      <div className="font-bold text-accent">Adaptive</div>
                      <div className="text-[10px] text-zinc-500 mt-0.5 leading-tight">Feature & Capacity Weighted</div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setStrategy('fixed')}
                      className={`p-2.5 rounded border text-left transition-colors ${
                        strategy === 'fixed'
                          ? 'border-accent bg-accent/10 text-zinc-200 font-semibold shadow-sm'
                          : 'border-canvas-borderSubtle bg-canvas-elevated/60 text-zinc-400 hover:text-zinc-300'
                      }`}
                    >
                      <div className="font-bold text-zinc-300">Fixed Baseline</div>
                      <div className="text-[10px] text-zinc-500 mt-0.5 leading-tight">Equal split + Water-filling</div>
                    </button>
                  </div>
                </div>

                {/* Password Input */}
                <div className="space-y-1.5">
                  <label htmlFor="multimodal-pass" className="text-xs font-mono text-zinc-300 font-medium block">
                    Passphrase (PBKDF2-HMAC-SHA256)
                  </label>
                  <input
                    id="multimodal-pass"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Optional passphrase (or auto-generate random 256-bit key)"
                    className="w-full rounded border border-canvas-border bg-canvas-elevated/70 px-3 py-2 text-xs font-mono text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-accent"
                  />
                  <p className="text-[10px] font-mono text-zinc-500">
                    If omitted, a cryptographically secure 32-byte AES key will be generated.
                  </p>
                </div>
              </div>
            </div>

            {/* Error Message */}
            {embedError && (
              <div className="rounded border border-red-800/40 bg-red-950/20 p-3 text-xs font-mono text-red-300 flex items-start space-x-2">
                <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                <span>{embedError}</span>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={embedLoading || !imageFile || !audioFile || !videoFile || !message.trim()}
              className="w-full py-2.5 px-4 rounded text-xs font-mono font-semibold bg-accent text-zinc-950 hover:bg-accent/90 disabled:opacity-40 disabled:hover:bg-accent transition-colors flex items-center justify-center space-x-2 shadow-sm"
            >
              <Lock className={`w-4 h-4 ${embedLoading ? 'animate-spin' : ''}`} />
              <span>{embedLoading ? 'Encrypting, Partitioning & Embedding Across Carriers...' : 'Embed Across Triad & Generate Bundle ZIP'}</span>
            </button>
          </form>

          {/* ========================================================= */}
          {/* EMBEDDING RESULTS CARD                                    */}
          {/* ========================================================= */}
          {embedResult && (
            <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-5 animate-in fade-in duration-200">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-canvas-borderSubtle gap-3">
                <div className="space-y-0.5">
                  <div className="flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span className="text-sm font-semibold text-canvas-textPrimary font-mono">
                      Multimodal Embedding Complete & Verified
                    </span>
                  </div>
                  <p className="text-xs font-mono text-zinc-400">
                    Message ID: <span className="text-zinc-300 font-bold">{embedResult.message_id}</span>
                  </p>
                </div>

                {/* Direct ZIP Bundle Download */}
                <a
                  href={embedResult.zip_bundle_data_url}
                  download={embedResult.filename}
                  className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded text-xs font-mono font-semibold bg-emerald-500 text-zinc-950 hover:bg-emerald-400 transition-colors shadow-sm self-start sm:self-auto"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download Triad ZIP Bundle</span>
                </a>
              </div>

              {/* Allocation Breakdown Table */}
              <div className="space-y-2">
                <h3 className="text-xs font-mono font-semibold text-zinc-300 uppercase tracking-wider flex items-center space-x-1.5">
                  <BarChart3 className="w-3.5 h-3.5 text-accent" />
                  <span>Partition Allocation Report ({embedResult.strategy.toUpperCase()})</span>
                </h3>

                <div className="overflow-x-auto rounded border border-canvas-borderSubtle">
                  <table className="w-full text-left font-mono text-xs">
                    <thead className="bg-canvas-elevated text-zinc-400 border-b border-canvas-borderSubtle text-[11px] uppercase">
                      <tr>
                        <th className="py-2 px-3">Carrier</th>
                        <th className="py-2 px-3">Framing</th>
                        <th className="py-2 px-3">Envelope Payload</th>
                        <th className="py-2 px-3">Carrier Total</th>
                        <th className="py-2 px-3">Utilization</th>
                        <th className="py-2 px-3">Rationale</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-canvas-borderSubtle bg-canvas-elevated/40 text-zinc-300">
                      {Object.entries(embedResult.allocations).map(([ctype, alloc]) => (
                        <tr key={ctype} className="hover:bg-zinc-800/30">
                          <td className="py-2 px-3 font-semibold uppercase text-zinc-200">
                            {ctype}
                          </td>
                          <td className="py-2 px-3 text-zinc-400">
                            {ctype === 'image' ? 'PSTG (14B)' : ctype === 'audio' ? 'WSTG (14B)' : 'VSTG (14B)'}
                          </td>
                          <td className="py-2 px-3 text-accent font-bold">
                            {alloc.payload_bytes} B
                          </td>
                          <td className="py-2 px-3 text-zinc-400">
                            {alloc.total_carrier_payload_bytes} B
                          </td>
                          <td className="py-2 px-3">
                            <span className="text-zinc-300">{(alloc.utilization_ratio * 100).toFixed(2)}%</span>
                          </td>
                          <td className="py-2 px-3 text-[11px] text-zinc-400 max-w-xs truncate">
                            {alloc.reason}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Fidelity & Distortion Metrics Grid */}
              <div className="space-y-2">
                <h3 className="text-xs font-mono font-semibold text-zinc-300 uppercase tracking-wider flex items-center space-x-1.5">
                  <Cpu className="w-3.5 h-3.5 text-accent" />
                  <span>Objective Carrier Distortion Measurements</span>
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs">
                  {/* Image Metric */}
                  <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 space-y-1">
                    <span className="text-zinc-400 text-[11px] uppercase font-semibold">Image Carrier Fidelity</span>
                    <div className="flex justify-between items-baseline pt-1">
                      <span className="text-zinc-400">PSNR:</span>
                      <span className="text-accent font-bold">{embedResult.metrics.image.psnr_display}</span>
                    </div>
                    <div className="flex justify-between items-baseline text-[11px] text-zinc-500">
                      <span>SSIM:</span>
                      <span>{embedResult.metrics.image.ssim.toFixed(4)}</span>
                    </div>
                  </div>

                  {/* Audio Metric */}
                  <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 space-y-1">
                    <span className="text-zinc-400 text-[11px] uppercase font-semibold">Audio Carrier Fidelity</span>
                    <div className="flex justify-between items-baseline pt-1">
                      <span className="text-emerald-400">SNR:</span>
                      <span className="text-emerald-400 font-bold">{embedResult.metrics.audio.snr_display}</span>
                    </div>
                    <div className="flex justify-between items-baseline text-[11px] text-zinc-500">
                      <span>Norm MSE:</span>
                      <span>{embedResult.metrics.audio.mse.toExponential(2)}</span>
                    </div>
                  </div>

                  {/* Video Metric */}
                  <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 space-y-1">
                    <span className="text-zinc-400 text-[11px] uppercase font-semibold">Video Carrier Fidelity</span>
                    <div className="flex justify-between items-baseline pt-1">
                      <span className="text-purple-400">Avg PSNR:</span>
                      <span className="text-purple-400 font-bold">{embedResult.metrics.video.psnr_display}</span>
                    </div>
                    <div className="flex justify-between items-baseline text-[11px] text-zinc-500">
                      <span>Frame MSE:</span>
                      <span>{embedResult.metrics.video.average_mse.toFixed(4)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Key Management Info (For Researcher) */}
              <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated/80 p-4 space-y-3 font-mono text-xs">
                <div className="flex items-center space-x-2 text-zinc-200 font-semibold">
                  <Key className="w-4 h-4 text-accent" />
                  <span>Cryptographic Secrets (Do NOT share with carrier bundle!)</span>
                </div>
                <div className="space-y-2 text-[11px]">
                  <div>
                    <span className="text-zinc-500 block mb-0.5">32-Byte AES-256 Key (Base64):</span>
                    <div className="flex items-center space-x-2">
                      <code className="bg-zinc-950 p-1.5 rounded flex-1 truncate text-zinc-300 border border-zinc-800">
                        {embedResult.key}
                      </code>
                      <button
                        type="button"
                        onClick={() => {
                          navigator.clipboard.writeText(embedResult.key);
                          setCopiedKey(true);
                          setTimeout(() => setCopiedKey(false), 2000);
                        }}
                        className="p-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded border border-zinc-700"
                        title="Copy Key"
                      >
                        {copiedKey ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>

                  {embedResult.salt && (
                    <div>
                      <span className="text-zinc-500 block mb-0.5">PBKDF2 Salt (Base64):</span>
                      <code className="bg-zinc-950 p-1.5 rounded block text-zinc-300 border border-zinc-800">
                        {embedResult.salt}
                      </code>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================= */}
      {/* WORKFLOW: EXTRACT & REASSEMBLE                            */}
      {/* ========================================================= */}
      {activeWorkflow === 'extract' && (
        <div className="space-y-6">
          <form onSubmit={handleExtractMultimodal} className="space-y-6">
            <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center space-x-2">
                  <span className="w-6 h-6 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-400 font-mono text-xs flex items-center justify-center font-bold">
                    1
                  </span>
                  <h2 className="text-sm font-semibold text-canvas-textPrimary font-mono uppercase tracking-wider">
                    Upload Stego Carrier Data
                  </h2>
                </div>

                {/* Bundle vs Individual Toggle */}
                <div className="inline-flex rounded border border-canvas-border bg-canvas-elevated p-0.5 font-mono text-[11px]">
                  <button
                    type="button"
                    onClick={() => setExtractMode('zip')}
                    className={`px-2.5 py-1 rounded transition-colors ${
                      extractMode === 'zip' ? 'bg-zinc-800 text-zinc-200 font-semibold' : 'text-zinc-400'
                    }`}
                  >
                    ZIP Bundle Archive
                  </button>
                  <button
                    type="button"
                    onClick={() => setExtractMode('individual')}
                    className={`px-2.5 py-1 rounded transition-colors ${
                      extractMode === 'individual' ? 'bg-zinc-800 text-zinc-200 font-semibold' : 'text-zinc-400'
                    }`}
                  >
                    Individual 3 Carriers
                  </button>
                </div>
              </div>

              {/* Upload Input based on Mode */}
              {extractMode === 'zip' ? (
                <div className="rounded border border-dashed border-canvas-borderSubtle bg-canvas-elevated/40 p-6 text-center space-y-2">
                  <Archive className="w-8 h-8 text-accent mx-auto" />
                  <p className="text-xs font-mono text-zinc-300 font-medium">
                    Upload Stego Multimodal Bundle (.zip)
                  </p>
                  <input
                    type="file"
                    accept=".zip,application/zip"
                    onChange={(e) => setZipBundleFile(e.target.files?.[0] || null)}
                    className="block w-full max-w-sm mx-auto text-xs font-mono text-zinc-400 file:mr-2 file:py-1 file:px-2.5 file:rounded file:border-0 file:text-[11px] file:font-mono file:bg-zinc-800 file:text-zinc-200 hover:file:bg-zinc-700 cursor-pointer"
                  />
                  {zipBundleFile && (
                    <p className="text-[11px] font-mono text-emerald-400">
                      Loaded: {zipBundleFile.name} ({(zipBundleFile.size / 1024).toFixed(1)} KB)
                    </p>
                  )}
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated/40 p-3 space-y-2">
                    <span className="text-xs font-mono text-zinc-300 font-semibold flex items-center space-x-1">
                      <ImageIcon className="w-3.5 h-3.5 text-accent" />
                      <span>Stego Image (.png)</span>
                    </span>
                    <input
                      type="file"
                      accept="image/png"
                      onChange={(e) => setExtractImageFile(e.target.files?.[0] || null)}
                      className="block w-full text-[11px] font-mono text-zinc-400"
                    />
                  </div>

                  <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated/40 p-3 space-y-2">
                    <span className="text-xs font-mono text-zinc-300 font-semibold flex items-center space-x-1">
                      <Music className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Stego Audio (.wav)</span>
                    </span>
                    <input
                      type="file"
                      accept="audio/wav"
                      onChange={(e) => setExtractAudioFile(e.target.files?.[0] || null)}
                      className="block w-full text-[11px] font-mono text-zinc-400"
                    />
                  </div>

                  <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated/40 p-3 space-y-2">
                    <span className="text-xs font-mono text-zinc-300 font-semibold flex items-center space-x-1">
                      <VideoIcon className="w-3.5 h-3.5 text-purple-400" />
                      <span>Stego Video (.avi)</span>
                    </span>
                    <input
                      type="file"
                      accept="video/avi,video/x-msvideo"
                      onChange={(e) => setExtractVideoFile(e.target.files?.[0] || null)}
                      className="block w-full text-[11px] font-mono text-zinc-400"
                    />
                  </div>
                </div>
              )}

              {/* Decryption Credentials */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-3 border-t border-canvas-borderSubtle">
                <div className="space-y-1.5">
                  <label htmlFor="ext-pass" className="text-xs font-mono text-zinc-300 font-medium block">
                    Decryption Passphrase
                  </label>
                  <input
                    id="ext-pass"
                    type="password"
                    value={extractPassword}
                    onChange={(e) => setExtractPassword(e.target.value)}
                    placeholder="Enter passphrase used during embedding"
                    className="w-full rounded border border-canvas-border bg-canvas-elevated/70 px-3 py-2 text-xs font-mono text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-accent"
                  />
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="ext-key" className="text-xs font-mono text-zinc-300 font-medium block">
                    Or Direct 32-Byte AES Key (Base64)
                  </label>
                  <input
                    id="ext-key"
                    type="text"
                    value={extractKey}
                    onChange={(e) => setExtractKey(e.target.value)}
                    placeholder="e.g. 44-character base64 AES key"
                    className="w-full rounded border border-canvas-border bg-canvas-elevated/70 px-3 py-2 text-xs font-mono text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-accent"
                  />
                </div>

                {extractPassword && extractMode !== 'zip' && (
                  <div className="space-y-1.5 sm:col-span-2">
                    <label htmlFor="ext-salt" className="text-xs font-mono text-zinc-300 font-medium block">
                      PBKDF2 Salt (Base64)
                    </label>
                    <input
                      id="ext-salt"
                      type="text"
                      value={extractSalt}
                      onChange={(e) => setExtractSalt(e.target.value)}
                      placeholder="Required when using passphrase with separate carriers"
                      className="w-full rounded border border-canvas-border bg-canvas-elevated/70 px-3 py-2 text-xs font-mono text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-accent"
                    />
                  </div>
                )}
              </div>
            </div>

            {extractError && (
              <div className="rounded border border-red-800/40 bg-red-950/20 p-3 text-xs font-mono text-red-300 flex items-start space-x-2">
                <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                <span>{extractError}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={extractLoading}
              className="w-full py-2.5 px-4 rounded text-xs font-mono font-semibold bg-emerald-500 text-zinc-950 hover:bg-emerald-400 disabled:opacity-40 transition-colors flex items-center justify-center space-x-2 shadow-sm"
            >
              <Unlock className={`w-4 h-4 ${extractLoading ? 'animate-spin' : ''}`} />
              <span>{extractLoading ? 'Extracting Chunks & Authenticating Decryption...' : 'Extract, Reassemble & Decrypt'}</span>
            </button>
          </form>

          {/* ========================================================= */}
          {/* EXTRACTION RESULTS CARD                                   */}
          {/* ========================================================= */}
          {extractResult && (
            <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-4 animate-in fade-in duration-200">
              <div className="flex items-center space-x-2 pb-3 border-b border-canvas-borderSubtle">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <div>
                  <h3 className="text-sm font-semibold text-canvas-textPrimary font-mono">
                    Multimodal Secret Authenticated & Recovered
                  </h3>
                  <p className="text-[11px] font-mono text-zinc-400">
                    Message UUID: <span className="text-zinc-300 font-bold">{extractResult.message_id}</span>
                  </p>
                </div>
              </div>

              {/* Chunk Reassembly Audit */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-xs">
                <div className="rounded bg-canvas-elevated p-2 border border-canvas-borderSubtle">
                  <span className="text-zinc-500 text-[10px] block uppercase">Chunks Recovered</span>
                  <span className="text-emerald-400 font-bold">{extractResult.chunk_count} of 3</span>
                </div>
                <div className="rounded bg-canvas-elevated p-2 border border-canvas-borderSubtle">
                  <span className="text-zinc-500 text-[10px] block uppercase">Image Slice</span>
                  <span className="text-zinc-200 font-bold">{extractResult.chunk_sizes.image} B</span>
                </div>
                <div className="rounded bg-canvas-elevated p-2 border border-canvas-borderSubtle">
                  <span className="text-zinc-500 text-[10px] block uppercase">Audio Slice</span>
                  <span className="text-zinc-200 font-bold">{extractResult.chunk_sizes.audio} B</span>
                </div>
                <div className="rounded bg-canvas-elevated p-2 border border-canvas-borderSubtle">
                  <span className="text-zinc-500 text-[10px] block uppercase">Video Slice</span>
                  <span className="text-zinc-200 font-bold">{extractResult.chunk_sizes.video} B</span>
                </div>
              </div>

              {/* Plaintext Box */}
              <div className="space-y-1.5 pt-2">
                <div className="flex justify-between items-center text-xs font-mono">
                  <span className="text-zinc-300 font-semibold uppercase tracking-wider">
                    Decrypted Plaintext
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(extractResult.plaintext);
                      setCopiedPlaintext(true);
                      setTimeout(() => setCopiedPlaintext(false), 2000);
                    }}
                    className="inline-flex items-center space-x-1 text-accent hover:underline text-[11px]"
                  >
                    {copiedPlaintext ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedPlaintext ? 'Copied' : 'Copy Plaintext'}</span>
                  </button>
                </div>
                <div className="rounded border border-canvas-border bg-canvas-elevated p-4 text-xs font-mono text-zinc-100 whitespace-pre-wrap select-all">
                  {extractResult.plaintext}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
