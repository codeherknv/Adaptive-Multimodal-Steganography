import React, { useState } from 'react';
import { 
  Unlock, 
  Upload, 
  Image as ImageIcon,
  Music,
  Video as VideoIcon,
  CheckCircle2, 
  AlertTriangle, 
  Copy, 
  Check, 
  Key, 
  ShieldCheck, 
  ArrowRight
} from 'lucide-react';
import { 
  extractFromImage, 
  extractFromAudio,
  extractFromVideo,
  decryptMessage 
} from '../api/client';
import { 
  ImageExtractResponse, 
  AudioExtractResponse,
  VideoExtractResponse,
  DecryptResponse 
} from '../api/types';

export const Receiver: React.FC = () => {
  // Carrier mode
  const [carrierType, setCarrierType] = useState<'image' | 'audio' | 'video'>('image');

  // Stego file states
  const [stegoFile, setStegoFile] = useState<File | null>(null);
  const [stegoPreview, setStegoPreview] = useState<string | null>(null);

  // Extraction states
  const [extracting, setExtracting] = useState<boolean>(false);
  const [extractResult, setExtractResult] = useState<ImageExtractResponse | AudioExtractResponse | VideoExtractResponse | null>(null);

  // Decryption states
  const [keyInput, setKeyInput] = useState<string>('');
  const [decryptMode, setDecryptMode] = useState<'key' | 'password'>('key');
  const [passwordInput, setPasswordInput] = useState<string>('');
  const [saltInput, setSaltInput] = useState<string>('');
  const [decrypting, setDecrypting] = useState<boolean>(false);
  const [decryptResult, setDecryptResult] = useState<DecryptResponse | null>(null);

  // Error handling
  const [error, setError] = useState<string | null>(null);
  const [copiedPlaintext, setCopiedPlaintext] = useState<boolean>(false);

  // Handle Stego file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setExtractResult(null);
    setDecryptResult(null);

    const file = e.target.files?.[0];
    if (!file) return;

    if (carrierType === 'image') {
      if (!file.name.toLowerCase().endsWith('.png') && file.type !== 'image/png') {
        setError('Please select a PNG carrier file.');
        return;
      }
      setStegoFile(file);
      const reader = new FileReader();
      reader.onload = () => setStegoPreview(reader.result as string);
      reader.readAsDataURL(file);
    } else if (carrierType === 'audio') {
      if (!file.name.toLowerCase().endsWith('.wav') && !file.type.includes('wav')) {
        setError('Please select a WAV audio carrier file.');
        return;
      }
      setStegoFile(file);
      setStegoPreview(URL.createObjectURL(file));
    } else {
      const lower = file.name.toLowerCase();
      if (!['.avi', '.mkv', '.mp4'].some(ext => lower.endsWith(ext))) {
        setError('Please select a valid video carrier file (.avi, .mkv, or .mp4).');
        return;
      }
      setStegoFile(file);
      setStegoPreview(file.name);
    }
  };

  // Step 1: Extract envelope from carrier
  const handleExtract = async () => {
    if (!stegoFile) {
      setError(`Please select a stego ${carrierType === 'image' ? 'PNG image' : carrierType === 'audio' ? 'WAV audio' : 'video'} file.`);
      return;
    }

    setExtracting(true);
    setError(null);
    setExtractResult(null);
    setDecryptResult(null);

    try {
      if (carrierType === 'image') {
        const result = await extractFromImage(stegoFile, 'base64');
        setExtractResult(result);
      } else if (carrierType === 'audio') {
        const result = await extractFromAudio(stegoFile, 'base64');
        setExtractResult(result);
      } else {
        const result = await extractFromVideo(stegoFile, 'base64');
        setExtractResult(result);
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Extraction failed.';
      setError(`Extraction Error: ${msg}`);
    } finally {
      setExtracting(false);
    }
  };

  // Step 2: Authenticate and decrypt envelope
  const handleDecrypt = async () => {
    if (!extractResult) {
      setError('Extract the envelope from the carrier file first.');
      return;
    }

    if (decryptMode === 'key' && !keyInput.trim()) {
      setError('Please supply the 32-byte AES key.');
      return;
    }

    if (decryptMode === 'password' && (!passwordInput.trim() || !saltInput.trim())) {
      setError('Please provide both the passphrase and the salt for PBKDF2 derivation.');
      return;
    }

    setDecrypting(true);
    setError(null);

    try {
      const decReq = {
        envelope: extractResult.envelope,
        encoding: 'base64' as const,
        ...(decryptMode === 'key' ? { key: keyInput.trim() } : {}),
        ...(decryptMode === 'password'
          ? { password: passwordInput.trim(), salt: saltInput.trim() }
          : {}),
      };

      const result = await decryptMessage(decReq);
      setDecryptResult(result);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Decryption failed.';
      setError(`Decryption Error: ${msg}`);
    } finally {
      setDecrypting(false);
    }
  };

  const copyPlaintext = () => {
    if (!decryptResult?.plaintext) return;
    navigator.clipboard.writeText(decryptResult.plaintext);
    setCopiedPlaintext(true);
    setTimeout(() => setCopiedPlaintext(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Title & Context */}
      <div className="border border-canvas-border bg-canvas-surface rounded-lg p-5 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-canvas-border">
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-base font-bold text-canvas-textPrimary tracking-tight">
                Receiver: Extraction & Authenticated Decryption
              </h1>
            </div>
            <p className="text-xs text-canvas-textMuted mt-1">
              Upload a stego PNG image, WAV audio, or video carrier, extract the embedded binary envelope, and authenticate with AES-256-GCM.
            </p>
          </div>

          {/* Carrier Switch */}
          <div className="flex items-center space-x-1.5 bg-canvas-elevated p-1 rounded border border-canvas-border text-xs font-mono">
            <button
              type="button"
              onClick={() => {
                setCarrierType('image');
                setStegoFile(null);
                setStegoPreview(null);
                setExtractResult(null);
                setDecryptResult(null);
                setError(null);
              }}
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
              onClick={() => {
                setCarrierType('audio');
                setStegoFile(null);
                setStegoPreview(null);
                setExtractResult(null);
                setDecryptResult(null);
                setError(null);
              }}
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
              onClick={() => {
                setCarrierType('video');
                setStegoFile(null);
                setStegoPreview(null);
                setExtractResult(null);
                setDecryptResult(null);
                setError(null);
              }}
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

      {/* Main 2-Step Extraction Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Step 1: Upload Stego Carrier & Extract */}
        <div className="border border-canvas-border bg-canvas-surface rounded-lg p-5 space-y-4">
          <div className="flex items-center space-x-2 text-xs font-mono text-canvas-textPrimary font-semibold pb-2 border-b border-canvas-border">
            {carrierType === 'image' ? (
              <ImageIcon className="w-3.5 h-3.5 text-accent" />
            ) : carrierType === 'audio' ? (
              <Music className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <VideoIcon className="w-3.5 h-3.5 text-purple-400" />
            )}
            <span>1. Upload Stego {carrierType === 'image' ? 'PNG Image' : carrierType === 'audio' ? 'PCM WAV Audio' : 'Video'}</span>
          </div>

          <div>
            <label className="block text-xs font-mono text-canvas-textMuted mb-1.5">
              Select Stego Carrier File:
            </label>
            <label className="border border-dashed border-canvas-border hover:border-zinc-600 bg-canvas-base rounded-md p-4 flex flex-col items-center justify-center cursor-pointer transition-colors">
              <Upload className="w-6 h-6 text-canvas-textMuted mb-1" />
              <span className="text-xs font-mono text-canvas-textSecondary">
                {stegoFile ? stegoFile.name : `Click or drop a stego ${carrierType === 'image' ? 'PNG' : carrierType === 'audio' ? 'WAV' : 'video'} here`}
              </span>
              <span className="text-[10px] font-mono text-zinc-500 mt-0.5">
                {carrierType === 'image' ? 'PNG carrier with PSTG header' : carrierType === 'audio' ? 'WAV audio carrier with WSTG header' : 'Lossless AVI/MKV carrier with VSTG header'}
              </span>
              <input
                type="file"
                accept={carrierType === 'image' ? 'image/png' : carrierType === 'audio' ? '.wav,audio/wav,audio/x-wav' : '.avi,.mkv,.mp4,video/*'}
                onChange={handleFileChange}
                className="hidden"
              />
            </label>
          </div>

          {/* Stego Preview */}
          {stegoPreview && (
            <div className="p-3 rounded bg-canvas-elevated border border-canvas-border text-xs font-mono space-y-2">
              {carrierType === 'image' ? (
                <div className="flex items-center space-x-3">
                  <img
                    src={stegoPreview}
                    alt="Stego Preview"
                    className="w-16 h-16 object-contain bg-zinc-950 rounded border border-canvas-border shrink-0"
                  />
                  <div className="flex-1 space-y-1">
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">File:</span>
                      <span className="text-canvas-textPrimary truncate">{stegoFile?.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Size:</span>
                      <span className="text-canvas-textPrimary">{stegoFile ? (stegoFile.size / 1024).toFixed(1) : 0} KB</span>
                    </div>
                  </div>
                </div>
              ) : carrierType === 'audio' ? (
                <div className="space-y-2">
                  <audio controls src={stegoPreview} className="w-full h-8" />
                  <div className="flex justify-between">
                    <span className="text-canvas-textMuted">File:</span>
                    <span className="text-canvas-textPrimary truncate">{stegoFile?.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-canvas-textMuted">Size:</span>
                    <span className="text-canvas-textPrimary">{stegoFile ? (stegoFile.size / 1024).toFixed(1) : 0} KB</span>
                  </div>
                </div>
              ) : (
                <div className="space-y-1">
                  <div className="flex items-center space-x-2 text-purple-400 font-semibold pb-1 border-b border-canvas-border">
                    <VideoIcon className="w-4 h-4" />
                    <span className="truncate">{stegoFile?.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-canvas-textMuted">Carrier Type:</span>
                    <span className="text-canvas-textPrimary">Lossless Video (.avi / .mkv)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-canvas-textMuted">File Size:</span>
                    <span className="text-canvas-textPrimary">{stegoFile ? (stegoFile.size / 1024).toFixed(1) : 0} KB</span>
                  </div>
                </div>
              )}
            </div>
          )}

          <button
            onClick={handleExtract}
            disabled={extracting || !stegoFile}
            className="w-full py-2.5 px-4 rounded bg-canvas-elevated hover:bg-zinc-800 border border-canvas-border disabled:opacity-40 text-canvas-textPrimary font-mono text-xs font-semibold flex items-center justify-center space-x-2 transition-colors cursor-pointer disabled:cursor-not-allowed"
          >
            {extracting ? (
              <span>Extracting LSB Payload...</span>
            ) : (
              <>
                <span>Extract Embedded Payload</span>
                <ArrowRight className="w-3.5 h-3.5 text-accent" />
              </>
            )}
          </button>

          {/* Extracted Envelope Inspection Card */}
          {extractResult && (
            <div className="border border-canvas-border bg-canvas-elevated rounded-md p-3.5 text-xs font-mono space-y-2">
              <div className="flex items-center justify-between pb-1 border-b border-canvas-border">
                <span className="text-emerald-400 font-semibold flex items-center space-x-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Envelope Extracted ({carrierType === 'image' ? 'PSTG' : carrierType === 'audio' ? 'WSTG' : 'VSTG'} Valid)</span>
                </span>
                <span className="text-zinc-500 text-[10px]">CRC32 Verified</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Envelope Size:</span>
                <span className="text-canvas-textPrimary">{extractResult.envelope_bytes_length} bytes</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Envelope Version:</span>
                <span className="text-canvas-textPrimary">v{extractResult.envelope_version}</span>
              </div>
              <div className="bg-canvas-base p-2 rounded border border-canvas-border break-all text-[11px] text-zinc-400 select-all max-h-16 overflow-y-auto">
                {extractResult.envelope}
              </div>
            </div>
          )}
        </div>

        {/* Step 2: Key & Decryption */}
        <div className="border border-canvas-border bg-canvas-surface rounded-lg p-5 space-y-4">
          <div className="flex items-center space-x-2 text-xs font-mono text-canvas-textPrimary font-semibold pb-2 border-b border-canvas-border">
            <Key className="w-3.5 h-3.5 text-accent" />
            <span>2. Key Authentication & Decryption</span>
          </div>

          <div>
            <label className="block text-xs font-mono text-canvas-textMuted mb-1.5">
              Decryption Authentication Mode:
            </label>
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              <button
                type="button"
                onClick={() => setDecryptMode('key')}
                className={`p-2 rounded border text-center transition-colors ${
                  decryptMode === 'key'
                    ? 'border-accent bg-accent/10 text-canvas-textPrimary'
                    : 'border-canvas-border bg-canvas-elevated text-canvas-textMuted hover:text-canvas-textSecondary'
                }`}
              >
                256-Bit Key
              </button>
              <button
                type="button"
                onClick={() => setDecryptMode('password')}
                className={`p-2 rounded border text-center transition-colors ${
                  decryptMode === 'password'
                    ? 'border-accent bg-accent/10 text-canvas-textPrimary'
                    : 'border-canvas-border bg-canvas-elevated text-canvas-textMuted hover:text-canvas-textSecondary'
                }`}
              >
                Passphrase + Salt
              </button>
            </div>
          </div>

          {decryptMode === 'key' ? (
            <div>
              <label className="block text-xs font-mono text-canvas-textMuted mb-1">
                Enter 32-Byte AES Key (Base64):
              </label>
              <input
                type="text"
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                placeholder="Paste key generated during encryption..."
                className="w-full text-xs font-mono p-2.5 rounded bg-canvas-base border border-canvas-border text-canvas-textPrimary focus:outline-none focus:border-accent"
              />
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-mono text-canvas-textMuted mb-1">
                  Passphrase:
                </label>
                <input
                  type="password"
                  value={passwordInput}
                  onChange={(e) => setPasswordInput(e.target.value)}
                  placeholder="Enter passphrase used to encrypt..."
                  className="w-full text-xs font-mono p-2.5 rounded bg-canvas-base border border-canvas-border text-canvas-textPrimary focus:outline-none focus:border-accent"
                />
              </div>
              <div>
                <label className="block text-xs font-mono text-canvas-textMuted mb-1">
                  PBKDF2 Salt (Base64):
                </label>
                <input
                  type="text"
                  value={saltInput}
                  onChange={(e) => setSaltInput(e.target.value)}
                  placeholder="Paste 16-byte salt from encryption..."
                  className="w-full text-xs font-mono p-2.5 rounded bg-canvas-base border border-canvas-border text-canvas-textPrimary focus:outline-none focus:border-accent"
                />
              </div>
            </div>
          )}

          <button
            onClick={handleDecrypt}
            disabled={decrypting || !extractResult}
            className="w-full py-2.5 px-4 rounded bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white font-mono text-xs font-semibold flex items-center justify-center space-x-2 transition-colors cursor-pointer disabled:cursor-not-allowed"
          >
            {decrypting ? (
              <span>Authenticating GCM Tag & Decrypting...</span>
            ) : (
              <>
                <Unlock className="w-3.5 h-3.5" />
                <span>Authenticate & Decrypt Payload</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Recovered Plaintext Output Box */}
      {decryptResult && (
        <div className="border border-emerald-900/60 bg-emerald-950/15 rounded-lg p-5 sm:p-6 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/40">
            <div className="flex items-center space-x-2 text-emerald-400 font-mono text-sm font-semibold">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Decryption Successful & GCM Tag Authenticated</span>
            </div>
            <button
              onClick={copyPlaintext}
              className="text-xs font-mono text-canvas-textSecondary hover:text-canvas-textPrimary flex items-center space-x-1 bg-canvas-elevated px-2.5 py-1 rounded border border-canvas-border"
            >
              {copiedPlaintext ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              <span>{copiedPlaintext ? 'Copied' : 'Copy Plaintext'}</span>
            </button>
          </div>

          <div className="space-y-1">
            <span className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider block">
              Recovered Plaintext ({decryptResult.plaintext_bytes_length} bytes):
            </span>
            <div className="p-4 rounded bg-canvas-base border border-canvas-border font-mono text-xs text-canvas-textPrimary whitespace-pre-wrap break-words select-all">
              {decryptResult.plaintext}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
