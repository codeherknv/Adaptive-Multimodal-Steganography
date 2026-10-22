import React, { useState } from 'react';
import { 
  Lock, 
  Upload, 
  Image as ImageIcon, 
  Music,
  Video as VideoIcon,
  CheckCircle2, 
  AlertTriangle, 
  Download, 
  Copy, 
  Check, 
  ShieldAlert,
  ArrowRight
} from 'lucide-react';
import { 
  checkImageCapacity, 
  checkAudioCapacity,
  checkVideoCapacity,
  encryptMessage, 
  embedInImage,
  embedInAudio,
  embedInVideo
} from '../api/client';
import { 
  ImageCapacityResponse, 
  ImageEmbedResponse, 
  AudioCapacityResponse,
  AudioEmbedResponse,
  VideoCapacityResponse,
  VideoEmbedResponse,
  EncryptResponse 
} from '../api/types';

export const Sender: React.FC = () => {
  // Carrier mode
  const [carrierType, setCarrierType] = useState<'image' | 'audio' | 'video'>('image');

  // Input states
  const [plaintext, setPlaintext] = useState<string>('Top Secret Multimodal Research Payload: 33/33/34 allocation baseline.');
  const [keyMode, setKeyMode] = useState<'auto' | 'custom' | 'password'>('auto');
  const [customKey, setCustomKey] = useState<string>('');
  const [password, setPassword] = useState<string>('');

  // Image carrier file states
  const [coverImageFile, setCoverImageFile] = useState<File | null>(null);
  const [coverImagePreview, setCoverImagePreview] = useState<string | null>(null);
  const [imageCapacity, setImageCapacity] = useState<ImageCapacityResponse | null>(null);
  const [imageCapacityLoading, setImageCapacityLoading] = useState<boolean>(false);

  // Audio carrier file states
  const [coverAudioFile, setCoverAudioFile] = useState<File | null>(null);
  const [coverAudioPreview, setCoverAudioPreview] = useState<string | null>(null);
  const [audioCapacity, setAudioCapacity] = useState<AudioCapacityResponse | null>(null);
  const [audioCapacityLoading, setAudioCapacityLoading] = useState<boolean>(false);

  // Video carrier file states
  const [coverVideoFile, setCoverVideoFile] = useState<File | null>(null);
  const [videoCapacity, setVideoCapacity] = useState<VideoCapacityResponse | null>(null);
  const [videoCapacityLoading, setVideoCapacityLoading] = useState<boolean>(false);

  // Execution states
  const [processing, setProcessing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [encryptResult, setEncryptResult] = useState<EncryptResponse | null>(null);
  const [imageEmbedResult, setImageEmbedResult] = useState<ImageEmbedResponse | null>(null);
  const [audioEmbedResult, setAudioEmbedResult] = useState<AudioEmbedResponse | null>(null);
  const [videoEmbedResult, setVideoEmbedResult] = useState<VideoEmbedResponse | null>(null);

  // Clipboard copy feedback
  const [copiedKey, setCopiedKey] = useState<boolean>(false);

  // Handle Cover PNG selection
  const handleImageFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setImageEmbedResult(null);
    setEncryptResult(null);

    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.png') && file.type !== 'image/png') {
      setError('Please select a lossless PNG image. JPEG and lossy formats destroy LSB data.');
      return;
    }

    setCoverImageFile(file);
    const reader = new FileReader();
    reader.onload = () => setCoverImagePreview(reader.result as string);
    reader.readAsDataURL(file);

    setImageCapacityLoading(true);
    try {
      const capData = await checkImageCapacity(file);
      setImageCapacity(capData);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(`Failed to inspect carrier image: ${err.message}`);
      } else {
        setError('Failed to calculate carrier image capacity.');
      }
      setImageCapacity(null);
    } finally {
      setImageCapacityLoading(false);
    }
  };

  // Handle Cover WAV selection
  const handleAudioFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setAudioEmbedResult(null);
    setEncryptResult(null);

    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.wav') && !file.type.includes('wav')) {
      setError('Please select an uncompressed PCM WAV audio file.');
      return;
    }

    setCoverAudioFile(file);
    const audioUrl = URL.createObjectURL(file);
    setCoverAudioPreview(audioUrl);

    setAudioCapacityLoading(true);
    try {
      const capData = await checkAudioCapacity(file);
      setAudioCapacity(capData);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(`Failed to inspect audio carrier: ${err.message}`);
      } else {
        setError('Failed to calculate audio carrier capacity.');
      }
      setAudioCapacity(null);
    } finally {
      setAudioCapacityLoading(false);
    }
  };

  // Handle Cover Video selection
  const handleVideoFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setVideoEmbedResult(null);
    setEncryptResult(null);

    const file = e.target.files?.[0];
    if (!file) return;

    const lowerName = file.name.toLowerCase();
    const validExts = ['.avi', '.mkv', '.mp4'];
    if (!validExts.some(ext => lowerName.endsWith(ext))) {
      setError('Please select a supported video file (.avi, .mkv, or .mp4).');
      return;
    }

    setCoverVideoFile(file);
    setVideoCapacityLoading(true);
    try {
      const capData = await checkVideoCapacity(file);
      setVideoCapacity(capData);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(`Failed to inspect video carrier: ${err.message}`);
      } else {
        setError('Failed to calculate video carrier capacity.');
      }
      setVideoCapacity(null);
    } finally {
      setVideoCapacityLoading(false);
    }
  };

  // Execute full Encrypt + Embed Pipeline
  const handleEncryptAndEmbed = async () => {
    if (!plaintext.trim()) {
      setError('Please enter a secret message to encrypt.');
      return;
    }

    if (carrierType === 'image' && !coverImageFile) {
      setError('Please select a PNG cover image carrier.');
      return;
    }

    if (carrierType === 'audio' && !coverAudioFile) {
      setError('Please select a PCM WAV cover audio carrier.');
      return;
    }

    if (carrierType === 'video' && !coverVideoFile) {
      setError('Please select a video cover carrier (.avi, .mkv, .mp4).');
      return;
    }

    setProcessing(true);
    setError(null);

    try {
      // Step 1: Encrypt via Phase 2 AES-256-GCM endpoint
      const encReq = {
        plaintext,
        encoding: 'base64' as const,
        ...(keyMode === 'custom' && customKey ? { key: customKey.trim() } : {}),
        ...(keyMode === 'password' && password ? { password: password.trim() } : {}),
      };

      const encResponse = await encryptMessage(encReq);
      setEncryptResult(encResponse);

      // Step 2: Embed into chosen carrier
      if (carrierType === 'image' && coverImageFile) {
        const embedResponse = await embedInImage(
          coverImageFile,
          encResponse.envelope,
          'base64'
        );
        setImageEmbedResult(embedResponse);
        setAudioEmbedResult(null);
        setVideoEmbedResult(null);
      } else if (carrierType === 'audio' && coverAudioFile) {
        const embedResponse = await embedInAudio(
          coverAudioFile,
          encResponse.envelope,
          'base64'
        );
        setAudioEmbedResult(embedResponse);
        setImageEmbedResult(null);
        setVideoEmbedResult(null);
      } else if (carrierType === 'video' && coverVideoFile) {
        const embedResponse = await embedInVideo(
          coverVideoFile,
          encResponse.envelope,
          'base64'
        );
        setVideoEmbedResult(embedResponse);
        setImageEmbedResult(null);
        setAudioEmbedResult(null);
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Operation failed.';
      setError(`Pipeline Error: ${msg}`);
    } finally {
      setProcessing(false);
    }
  };

  const copyKeyToClipboard = () => {
    if (!encryptResult?.key) return;
    navigator.clipboard.writeText(encryptResult.key);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const estimatedPayloadBytes = new TextEncoder().encode(plaintext).length + 30; // ~30 bytes envelope overhead

  return (
    <div className="space-y-6">
      {/* Title & Context */}
      <div className="border border-canvas-border bg-canvas-surface rounded-lg p-5 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-canvas-border">
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-mono text-xs text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">
                Phase 5 Live
              </span>
              <h1 className="text-base font-bold text-canvas-textPrimary tracking-tight">
                Sender: Multimodal Carrier Steganography
              </h1>
            </div>
            <p className="text-xs text-canvas-textMuted mt-1">
              Encrypt secret plaintext with authenticated AES-256-GCM and embed the envelope into lossless PNG pixels, PCM WAV audio samples, or video carrier frames using LSB substitution.
            </p>
          </div>

          {/* Carrier Switch */}
          <div className="flex items-center space-x-1.5 bg-canvas-elevated p-1 rounded border border-canvas-border text-xs font-mono">
            <button
              type="button"
              onClick={() => { setCarrierType('image'); setError(null); }}
              className={`px-3 py-1 rounded transition-colors flex items-center space-x-1.5 ${
                carrierType === 'image'
                  ? 'bg-canvas-base text-canvas-textPrimary border border-canvas-border shadow-sm'
                  : 'text-canvas-textMuted hover:text-canvas-textSecondary'
              }`}
            >
              <ImageIcon className="w-3.5 h-3.5 text-accent" />
              <span>PNG Image</span>
            </button>
            <button
              type="button"
              onClick={() => { setCarrierType('audio'); setError(null); }}
              className={`px-3 py-1 rounded transition-colors flex items-center space-x-1.5 ${
                carrierType === 'audio'
                  ? 'bg-canvas-base text-canvas-textPrimary border border-canvas-border shadow-sm'
                  : 'text-canvas-textMuted hover:text-canvas-textSecondary'
              }`}
            >
              <Music className="w-3.5 h-3.5 text-emerald-400" />
              <span>WAV Audio</span>
            </button>
            <button
              type="button"
              onClick={() => { setCarrierType('video'); setError(null); }}
              className={`px-3 py-1 rounded transition-colors flex items-center space-x-1.5 ${
                carrierType === 'video'
                  ? 'bg-canvas-base text-canvas-textPrimary border border-canvas-border shadow-sm'
                  : 'text-canvas-textMuted hover:text-canvas-textSecondary'
              }`}
            >
              <VideoIcon className="w-3.5 h-3.5 text-purple-400" />
              <span>Video</span>
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 border border-rose-900/60 bg-rose-950/20 rounded p-3 text-xs text-rose-300 flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Main 2-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Left Column: Message & Key Configuration */}
        <div className="border border-canvas-border bg-canvas-surface rounded-lg p-5 space-y-4">
          <div className="flex items-center space-x-2 text-xs font-mono text-canvas-textPrimary font-semibold pb-2 border-b border-canvas-border">
            <Lock className="w-3.5 h-3.5 text-accent" />
            <span>1. Secret Message & Cryptographic Key</span>
          </div>

          <div>
            <label className="block text-xs font-mono text-canvas-textMuted mb-1.5">
              Secret Plaintext ({plaintext.length} chars, ~{estimatedPayloadBytes} bytes framed):
            </label>
            <textarea
              rows={4}
              value={plaintext}
              onChange={(e) => setPlaintext(e.target.value)}
              placeholder="Enter secret text to conceal..."
              className="w-full text-xs font-mono p-3 rounded bg-canvas-base border border-canvas-border text-canvas-textPrimary focus:outline-none focus:border-accent resize-none"
            />
          </div>

          <div>
            <label className="block text-xs font-mono text-canvas-textMuted mb-1.5">
              Key Management Mode:
            </label>
            <div className="grid grid-cols-3 gap-2 text-xs font-mono">
              <button
                type="button"
                onClick={() => setKeyMode('auto')}
                className={`p-2 rounded border text-center transition-colors ${
                  keyMode === 'auto'
                    ? 'border-accent bg-accent/10 text-canvas-textPrimary'
                    : 'border-canvas-border bg-canvas-elevated text-canvas-textMuted hover:text-canvas-textSecondary'
                }`}
              >
                Auto-Generate
              </button>
              <button
                type="button"
                onClick={() => setKeyMode('custom')}
                className={`p-2 rounded border text-center transition-colors ${
                  keyMode === 'custom'
                    ? 'border-accent bg-accent/10 text-canvas-textPrimary'
                    : 'border-canvas-border bg-canvas-elevated text-canvas-textMuted hover:text-canvas-textSecondary'
                }`}
              >
                Custom Key
              </button>
              <button
                type="button"
                onClick={() => setKeyMode('password')}
                className={`p-2 rounded border text-center transition-colors ${
                  keyMode === 'password'
                    ? 'border-accent bg-accent/10 text-canvas-textPrimary'
                    : 'border-canvas-border bg-canvas-elevated text-canvas-textMuted hover:text-canvas-textSecondary'
                }`}
              >
                Passphrase
              </button>
            </div>
          </div>

          {keyMode === 'custom' && (
            <div>
              <label className="block text-xs font-mono text-canvas-textMuted mb-1">
                Custom 32-Byte AES Key (Base64):
              </label>
              <input
                type="text"
                value={customKey}
                onChange={(e) => setCustomKey(e.target.value)}
                placeholder="e.g. kxOFT9apH+J7RENU9pE/GqIWC1IK7RcTA/9LrxTTw/s="
                className="w-full text-xs font-mono p-2 rounded bg-canvas-base border border-canvas-border text-canvas-textPrimary focus:outline-none focus:border-accent"
              />
            </div>
          )}

          {keyMode === 'password' && (
            <div>
              <label className="block text-xs font-mono text-canvas-textMuted mb-1">
                Passphrase (Derived via PBKDF2-HMAC-SHA256, 600k rounds):
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter strong passphrase..."
                className="w-full text-xs font-mono p-2 rounded bg-canvas-base border border-canvas-border text-canvas-textPrimary focus:outline-none focus:border-accent"
              />
            </div>
          )}

          <div className="pt-2 text-[11px] font-mono text-canvas-textMuted bg-canvas-elevated/40 p-2.5 rounded border border-canvas-borderSubtle">
            <span className="text-accent font-semibold">Security Note:</span> AES-256-GCM uses a fresh 96-bit nonce for each execution. Plaintext is authenticated with a 128-bit tag before release.
          </div>
        </div>

        {/* Right Column: Carrier Selection & Capacity */}
        <div className="border border-canvas-border bg-canvas-surface rounded-lg p-5 space-y-4">
          <div className="flex items-center space-x-2 text-xs font-mono text-canvas-textPrimary font-semibold pb-2 border-b border-canvas-border">
            {carrierType === 'image' ? (
              <ImageIcon className="w-3.5 h-3.5 text-accent" />
            ) : carrierType === 'audio' ? (
              <Music className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <VideoIcon className="w-3.5 h-3.5 text-purple-400" />
            )}
            <span>2. Cover {carrierType === 'image' ? 'PNG Image' : carrierType === 'audio' ? 'PCM WAV Audio' : 'Video'} Carrier</span>
          </div>

          {/* Carrier Upload Area */}
          {carrierType === 'image' && (
            <div>
              <label className="block text-xs font-mono text-canvas-textMuted mb-1.5">
                Select Lossless Cover PNG:
              </label>
              <label className="border border-dashed border-canvas-border hover:border-zinc-600 bg-canvas-base rounded-md p-4 flex flex-col items-center justify-center cursor-pointer transition-colors">
                <Upload className="w-6 h-6 text-canvas-textMuted mb-1" />
                <span className="text-xs font-mono text-canvas-textSecondary">
                  {coverImageFile ? coverImageFile.name : 'Click or drop a PNG image here'}
                </span>
                <span className="text-[10px] font-mono text-zinc-500 mt-0.5">
                  PNG format required (Max 25 MB)
                </span>
                <input
                  type="file"
                  accept="image/png"
                  onChange={handleImageFileChange}
                  className="hidden"
                />
              </label>
            </div>
          )}

          {carrierType === 'audio' && (
            <div>
              <label className="block text-xs font-mono text-canvas-textMuted mb-1.5">
                Select Uncompressed PCM WAV Audio:
              </label>
              <label className="border border-dashed border-canvas-border hover:border-zinc-600 bg-canvas-base rounded-md p-4 flex flex-col items-center justify-center cursor-pointer transition-colors">
                <Music className="w-6 h-6 text-canvas-textMuted mb-1" />
                <span className="text-xs font-mono text-canvas-textSecondary">
                  {coverAudioFile ? coverAudioFile.name : 'Click or drop a WAV audio file here'}
                </span>
                <span className="text-[10px] font-mono text-zinc-500 mt-0.5">
                  Uncompressed PCM WAV (16-bit or 8-bit, Mono or Stereo)
                </span>
                <input
                  type="file"
                  accept=".wav,audio/wav,audio/x-wav"
                  onChange={handleAudioFileChange}
                  className="hidden"
                />
              </label>
            </div>
          )}

          {carrierType === 'video' && (
            <div>
              <label className="block text-xs font-mono text-canvas-textMuted mb-1.5">
                Select Video Carrier (.avi, .mkv, .mp4):
              </label>
              <label className="border border-dashed border-canvas-border hover:border-zinc-600 bg-canvas-base rounded-md p-4 flex flex-col items-center justify-center cursor-pointer transition-colors">
                <VideoIcon className="w-6 h-6 text-purple-400 mb-1" />
                <span className="text-xs font-mono text-canvas-textSecondary">
                  {coverVideoFile ? coverVideoFile.name : 'Click or drop a video file here'}
                </span>
                <span className="text-[10px] font-mono text-zinc-500 mt-0.5">
                  Lossless AVI / MKV (FFV1, HFYU) or MP4 cover video
                </span>
                <input
                  type="file"
                  accept=".avi,.mkv,.mp4,video/*"
                  onChange={handleVideoFileChange}
                  className="hidden"
                />
              </label>
            </div>
          )}

          {/* Carrier Preview & Capacity Info */}
          {carrierType === 'image' && coverImagePreview && (
            <div className="flex items-start space-x-4 p-3 rounded bg-canvas-elevated border border-canvas-border text-xs font-mono">
              <img
                src={coverImagePreview}
                alt="Cover Preview"
                className="w-20 h-20 object-contain bg-zinc-950 rounded border border-canvas-border shrink-0"
              />
              <div className="space-y-1 flex-1">
                <div className="flex justify-between">
                  <span className="text-canvas-textMuted">File Size:</span>
                  <span className="text-canvas-textPrimary">{coverImageFile ? (coverImageFile.size / 1024).toFixed(1) : 0} KB</span>
                </div>
                {imageCapacity && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Resolution:</span>
                      <span className="text-canvas-textPrimary">{imageCapacity.width} × {imageCapacity.height} ({imageCapacity.color_mode})</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Max Payload:</span>
                      <span className="text-emerald-400 font-semibold">{imageCapacity.max_usable_payload_bytes.toLocaleString()} bytes</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Required:</span>
                      <span className={`${estimatedPayloadBytes > imageCapacity.max_usable_payload_bytes ? 'text-rose-400 font-bold' : 'text-canvas-textPrimary'}`}>
                        {estimatedPayloadBytes} bytes
                      </span>
                    </div>
                  </>
                )}
                {imageCapacityLoading && (
                  <span className="text-zinc-500 italic">Calculating carrier capacity...</span>
                )}
              </div>
            </div>
          )}

          {carrierType === 'audio' && coverAudioFile && (
            <div className="p-3 rounded bg-canvas-elevated border border-canvas-border text-xs font-mono space-y-2">
              {coverAudioPreview && (
                <audio controls src={coverAudioPreview} className="w-full h-8" />
              )}
              <div className="space-y-1">
                <div className="flex justify-between">
                  <span className="text-canvas-textMuted">File Size:</span>
                  <span className="text-canvas-textPrimary">{(coverAudioFile.size / 1024).toFixed(1)} KB</span>
                </div>
                {audioCapacity && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Layout:</span>
                      <span className="text-canvas-textPrimary">{audioCapacity.channel_layout} • {audioCapacity.sample_rate / 1000} kHz • {audioCapacity.bits_per_sample}-bit</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Duration:</span>
                      <span className="text-canvas-textPrimary">{audioCapacity.duration_seconds.toFixed(2)}s ({audioCapacity.total_samples.toLocaleString()} samples)</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Max Payload:</span>
                      <span className="text-emerald-400 font-semibold">{audioCapacity.max_usable_payload_bytes.toLocaleString()} bytes</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Framing Overhead:</span>
                      <span className="text-zinc-500">14 bytes (WSTG header)</span>
                    </div>
                  </>
                )}
                {audioCapacityLoading && (
                  <span className="text-zinc-500 italic">Calculating audio capacity...</span>
                )}
              </div>
            </div>
          )}

          {carrierType === 'video' && coverVideoFile && (
            <div className="p-3 rounded bg-canvas-elevated border border-canvas-border text-xs font-mono space-y-2">
              <div className="flex items-center space-x-2 text-purple-400 font-semibold pb-1 border-b border-canvas-border">
                <VideoIcon className="w-4 h-4" />
                <span>{coverVideoFile.name} ({(coverVideoFile.size / 1024).toFixed(1)} KB)</span>
              </div>
              <div className="space-y-1">
                {videoCapacity && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Dimensions & FPS:</span>
                      <span className="text-canvas-textPrimary">{videoCapacity.width} × {videoCapacity.height} @ {videoCapacity.fps} fps</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Frames & Duration:</span>
                      <span className="text-canvas-textPrimary">{videoCapacity.num_frames} frames ({videoCapacity.duration_seconds.toFixed(2)}s)</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Lossless Codec:</span>
                      <span className="text-purple-400 font-semibold">{videoCapacity.recommended_codec} ({videoCapacity.container_format})</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Max Usable Payload:</span>
                      <span className="text-emerald-400 font-semibold">{videoCapacity.max_usable_payload_bytes.toLocaleString()} bytes</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Required Payload:</span>
                      <span className={estimatedPayloadBytes > videoCapacity.max_usable_payload_bytes ? 'text-rose-400 font-bold' : 'text-canvas-textPrimary'}>
                        {estimatedPayloadBytes} bytes
                      </span>
                    </div>
                  </>
                )}
                {videoCapacityLoading && (
                  <span className="text-zinc-500 italic">Inspecting video frames and codec...</span>
                )}
              </div>
            </div>
          )}

          {/* Action Button */}
          <button
            onClick={handleEncryptAndEmbed}
            disabled={
              processing ||
              (carrierType === 'image' && !coverImageFile) ||
              (carrierType === 'audio' && !coverAudioFile) ||
              (carrierType === 'video' && !coverVideoFile) ||
              !plaintext.trim()
            }
            className="w-full py-2.5 px-4 rounded bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white font-mono text-xs font-semibold flex items-center justify-center space-x-2 transition-colors cursor-pointer disabled:cursor-not-allowed"
          >
            {processing ? (
              <span>Encrypting & Embedding LSB...</span>
            ) : (
              <>
                <span>Encrypt & Embed into {carrierType === 'image' ? 'PNG' : carrierType === 'audio' ? 'WAV' : 'Video'}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Results & Stego Download Section (Image Result) */}
      {imageEmbedResult && carrierType === 'image' && (
        <div className="border border-emerald-900/60 bg-emerald-950/10 rounded-lg p-5 sm:p-6 space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/40">
            <div className="flex items-center space-x-2 text-emerald-400 font-mono text-sm font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Image Steganographic Embedding Succeeded</span>
            </div>
            <span className="text-xs font-mono text-zinc-400">
              Payload: {imageEmbedResult.embedded_bytes} bytes concealed
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            {/* Stego Image Preview & Download */}
            <div className="space-y-3">
              <span className="block text-xs font-mono text-canvas-textMuted uppercase tracking-wider">
                Generated Stego PNG Carrier:
              </span>
              <div className="border border-canvas-border bg-canvas-base rounded p-2 flex items-center justify-center">
                <img
                  src={imageEmbedResult.stego_image_data_url}
                  alt="Stego Output"
                  className="max-h-48 object-contain rounded"
                />
              </div>
              <a
                href={imageEmbedResult.stego_image_data_url}
                download={imageEmbedResult.filename}
                className="w-full py-2 px-3 rounded bg-canvas-elevated hover:bg-zinc-800 border border-canvas-border text-canvas-textPrimary font-mono text-xs flex items-center justify-center space-x-2 transition-colors"
              >
                <Download className="w-3.5 h-3.5 text-accent" />
                <span>Download Stego PNG</span>
              </a>
            </div>

            {/* Media Quality Metrics */}
            <div className="border border-canvas-border bg-canvas-elevated rounded-md p-4 space-y-3 text-xs font-mono">
              <span className="block text-canvas-textMuted uppercase tracking-wider text-[11px] pb-1 border-b border-canvas-border">
                Empirical Quality Distortion Metrics
              </span>

              <div className="space-y-2">
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">PSNR:</span>
                  <span className="text-emerald-400 font-bold text-sm">
                    {imageEmbedResult.metrics.psnr_display}
                  </span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Mean Squared Error (MSE):</span>
                  <span className="text-canvas-textPrimary">{imageEmbedResult.metrics.mse}</span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Structural Similarity (SSIM):</span>
                  <span className="text-canvas-textPrimary">{imageEmbedResult.metrics.ssim}</span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Bits Per Pixel (bpp):</span>
                  <span className="text-canvas-textPrimary">{imageEmbedResult.metrics.bits_per_pixel}</span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Carrier Capacity Used:</span>
                  <span className="text-canvas-textPrimary">{(imageEmbedResult.metrics.capacity_used_ratio * 100).toFixed(2)}%</span>
                </div>
              </div>

              <p className="text-[10px] text-zinc-500 pt-1 leading-relaxed">
                <span className="text-zinc-400 font-medium">Research Note:</span> PSNR &gt; 40 dB and SSIM ≈ 1.0 measure visual fidelity against the cover carrier; they do not prove security or resistance against statistical or machine-learning steganalysis.
              </p>
            </div>

            {/* Key Management Box */}
            <div className="border border-canvas-border bg-canvas-elevated rounded-md p-4 space-y-3 text-xs font-mono">
              <div className="flex items-center justify-between pb-1 border-b border-canvas-border">
                <span className="text-canvas-textMuted uppercase tracking-wider text-[11px]">
                  Decryption Key (Copy Now)
                </span>
                <button
                  onClick={copyKeyToClipboard}
                  className="hover:text-canvas-textPrimary p-1"
                  title="Copy Key"
                >
                  {copiedKey ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>

              <div className="bg-canvas-base p-2.5 rounded border border-canvas-border break-all select-all text-accent text-[11px]">
                {encryptResult?.key}
              </div>

              {encryptResult?.salt && (
                <div>
                  <span className="text-[10px] text-zinc-400 block mb-0.5">PBKDF2 Salt:</span>
                  <div className="bg-canvas-base p-1.5 rounded border border-canvas-border break-all select-all text-[10px] text-zinc-300">
                    {encryptResult.salt}
                  </div>
                </div>
              )}

              <div className="p-2.5 rounded bg-amber-950/20 border border-amber-900/40 text-amber-300/90 text-[10px] flex items-start space-x-1.5">
                <ShieldAlert className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-400" />
                <span>
                  <strong>Academic Key Hygiene:</strong> This key is <em>never</em> embedded inside the carrier. You must provide it to the Receiver to authenticate and decrypt the recovered message.
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Results & Stego Download Section (Audio Result) */}
      {audioEmbedResult && carrierType === 'audio' && (
        <div className="border border-emerald-900/60 bg-emerald-950/10 rounded-lg p-5 sm:p-6 space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/40">
            <div className="flex items-center space-x-2 text-emerald-400 font-mono text-sm font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Audio Steganographic Embedding Succeeded</span>
            </div>
            <span className="text-xs font-mono text-zinc-400">
              Payload: {audioEmbedResult.embedded_bytes} bytes concealed
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            {/* Stego Audio Player & Download */}
            <div className="space-y-3">
              <span className="block text-xs font-mono text-canvas-textMuted uppercase tracking-wider">
                Generated Stego WAV Carrier:
              </span>
              <div className="border border-canvas-border bg-canvas-base rounded p-3 flex flex-col justify-center space-y-2">
                <audio controls src={audioEmbedResult.stego_audio_data_url} className="w-full h-8" />
              </div>
              <a
                href={audioEmbedResult.stego_audio_data_url}
                download={audioEmbedResult.filename}
                className="w-full py-2 px-3 rounded bg-canvas-elevated hover:bg-zinc-800 border border-canvas-border text-canvas-textPrimary font-mono text-xs flex items-center justify-center space-x-2 transition-colors"
              >
                <Download className="w-3.5 h-3.5 text-emerald-400" />
                <span>Download Stego WAV</span>
              </a>
            </div>

            {/* Audio Quality Metrics */}
            <div className="border border-canvas-border bg-canvas-elevated rounded-md p-4 space-y-3 text-xs font-mono">
              <span className="block text-canvas-textMuted uppercase tracking-wider text-[11px] pb-1 border-b border-canvas-border">
                Audio Fidelity Metrics
              </span>

              <div className="space-y-2">
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Signal-to-Noise Ratio (SNR):</span>
                  <span className="text-emerald-400 font-bold text-sm">
                    {audioEmbedResult.metrics.snr_display}
                  </span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Normalized MSE:</span>
                  <span className="text-canvas-textPrimary">{audioEmbedResult.metrics.mse}</span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Carrier Capacity Used:</span>
                  <span className="text-canvas-textPrimary">{(audioEmbedResult.metrics.capacity_used_ratio * 100).toFixed(2)}%</span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Bits Per Sample Used:</span>
                  <span className="text-canvas-textPrimary">{audioEmbedResult.metrics.bits_per_sample_used}</span>
                </div>
              </div>

              <p className="text-[10px] text-zinc-500 pt-1 leading-relaxed">
                <span className="text-zinc-400 font-medium">Research Note:</span> Audio SNR and MSE quantify physical sample fidelity between cover and stego signals; they do not prove resistance against statistical or machine-learning audio steganalysis.
              </p>
            </div>

            {/* Key Management Box */}
            <div className="border border-canvas-border bg-canvas-elevated rounded-md p-4 space-y-3 text-xs font-mono">
              <div className="flex items-center justify-between pb-1 border-b border-canvas-border">
                <span className="text-canvas-textMuted uppercase tracking-wider text-[11px]">
                  Decryption Key (Copy Now)
                </span>
                <button
                  onClick={copyKeyToClipboard}
                  className="hover:text-canvas-textPrimary p-1"
                  title="Copy Key"
                >
                  {copiedKey ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>

              <div className="bg-canvas-base p-2.5 rounded border border-canvas-border break-all select-all text-accent text-[11px]">
                {encryptResult?.key}
              </div>

              {encryptResult?.salt && (
                <div>
                  <span className="text-[10px] text-zinc-400 block mb-0.5">PBKDF2 Salt:</span>
                  <div className="bg-canvas-base p-1.5 rounded border border-canvas-border break-all select-all text-[10px] text-zinc-300">
                    {encryptResult.salt}
                  </div>
                </div>
              )}

              <div className="p-2.5 rounded bg-amber-950/20 border border-amber-900/40 text-amber-300/90 text-[10px] flex items-start space-x-1.5">
                <ShieldAlert className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-400" />
                <span>
                  <strong>Academic Key Hygiene:</strong> This key is <em>never</em> embedded inside the carrier. You must provide it to the Receiver to authenticate and decrypt the recovered message.
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Results & Stego Download Section (Video Result) */}
      {videoEmbedResult && carrierType === 'video' && (
        <div className="border border-emerald-900/60 bg-emerald-950/10 rounded-lg p-5 sm:p-6 space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/40">
            <div className="flex items-center space-x-2 text-emerald-400 font-mono text-sm font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Video Steganographic Embedding Succeeded</span>
            </div>
            <span className="text-xs font-mono text-zinc-400">
              Payload: {videoEmbedResult.embedded_bytes} bytes concealed
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            {/* Stego Video Keyframe Preview & Download */}
            <div className="space-y-3">
              <span className="block text-xs font-mono text-canvas-textMuted uppercase tracking-wider">
                Stego Keyframe Preview & Output:
              </span>
              <div className="border border-canvas-border bg-canvas-base rounded p-2 flex flex-col items-center justify-center space-y-2">
                <img
                  src={videoEmbedResult.preview_frame_data_url}
                  alt="Stego Video Keyframe"
                  className="max-h-48 object-contain rounded"
                />
                <span className="text-[10px] font-mono text-zinc-500">
                  Frame 0 Keyframe Preview (Lossless FFV1 AVI)
                </span>
              </div>
              <a
                href={videoEmbedResult.stego_video_data_url}
                download={videoEmbedResult.filename}
                className="w-full py-2 px-3 rounded bg-canvas-elevated hover:bg-zinc-800 border border-canvas-border text-canvas-textPrimary font-mono text-xs flex items-center justify-center space-x-2 transition-colors"
              >
                <Download className="w-3.5 h-3.5 text-purple-400" />
                <span>Download Stego Video (.avi)</span>
              </a>
            </div>

            {/* Video Distortion Metrics */}
            <div className="border border-canvas-border bg-canvas-elevated rounded-md p-4 space-y-3 text-xs font-mono">
              <span className="block text-canvas-textMuted uppercase tracking-wider text-[11px] pb-1 border-b border-canvas-border">
                Video Fidelity Distortion Metrics
              </span>

              <div className="space-y-2">
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Average Frame PSNR:</span>
                  <span className="text-emerald-400 font-bold text-sm">
                    {videoEmbedResult.metrics.psnr_display}
                  </span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Average Frame MSE:</span>
                  <span className="text-canvas-textPrimary">{videoEmbedResult.metrics.average_mse}</span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Frames Modified:</span>
                  <span className="text-canvas-textPrimary">
                    {videoEmbedResult.metrics.modified_frames} / {videoEmbedResult.metrics.total_frames} frames
                  </span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Carrier Capacity Used:</span>
                  <span className="text-canvas-textPrimary">
                    {(videoEmbedResult.metrics.capacity_used_ratio * 100).toFixed(4)}%
                  </span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Resolution & FPS:</span>
                  <span className="text-canvas-textPrimary">
                    {videoEmbedResult.metrics.width}×{videoEmbedResult.metrics.height} @ {videoEmbedResult.metrics.fps} fps
                  </span>
                </div>
              </div>

              <p className="text-[10px] text-zinc-500 pt-1 leading-relaxed">
                <span className="text-zinc-400 font-medium">Research Note:</span> Average frame MSE and PSNR measure spatial pixel fidelity relative to cover frames; they do not prove security or resistance against statistical or machine-learning video steganalysis.
              </p>
            </div>

            {/* Key Management Box */}
            <div className="border border-canvas-border bg-canvas-elevated rounded-md p-4 space-y-3 text-xs font-mono">
              <div className="flex items-center justify-between pb-1 border-b border-canvas-border">
                <span className="text-canvas-textMuted uppercase tracking-wider text-[11px]">
                  Decryption Key (Copy Now)
                </span>
                <button
                  onClick={copyKeyToClipboard}
                  className="hover:text-canvas-textPrimary p-1"
                  title="Copy Key"
                >
                  {copiedKey ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>

              <div className="bg-canvas-base p-2.5 rounded border border-canvas-border break-all select-all text-accent text-[11px]">
                {encryptResult?.key}
              </div>

              {encryptResult?.salt && (
                <div>
                  <span className="text-[10px] text-zinc-400 block mb-0.5">PBKDF2 Salt:</span>
                  <div className="bg-canvas-base p-1.5 rounded border border-canvas-border break-all select-all text-[10px] text-zinc-300">
                    {encryptResult.salt}
                  </div>
                </div>
              )}

              <div className="p-2.5 rounded bg-amber-950/20 border border-amber-900/40 text-amber-300/90 text-[10px] flex items-start space-x-1.5">
                <ShieldAlert className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-400" />
                <span>
                  <strong>Academic Key Hygiene:</strong> This key is <em>never</em> embedded inside the carrier. You must provide it to the Receiver to authenticate and decrypt the recovered message.
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
