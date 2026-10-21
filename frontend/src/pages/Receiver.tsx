import React, { useState } from 'react';
import { 
  Unlock, 
  Upload, 
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
  decryptMessage 
} from '../api/client';
import { 
  ImageExtractResponse, 
  DecryptResponse 
} from '../api/types';

export const Receiver: React.FC = () => {
  // Stego file states
  const [stegoFile, setStegoFile] = useState<File | null>(null);
  const [stegoPreview, setStegoPreview] = useState<string | null>(null);

  // Extraction states
  const [extracting, setExtracting] = useState<boolean>(false);
  const [extractResult, setExtractResult] = useState<ImageExtractResponse | null>(null);

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

  // Handle Stego PNG file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setExtractResult(null);
    setDecryptResult(null);

    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.png') && file.type !== 'image/png') {
      setError('Please select a PNG carrier file.');
      return;
    }

    setStegoFile(file);
    const reader = new FileReader();
    reader.onload = () => setStegoPreview(reader.result as string);
    reader.readAsDataURL(file);
  };

  // Step 1: Extract envelope from image
  const handleExtract = async () => {
    if (!stegoFile) {
      setError('Please select a stego PNG image.');
      return;
    }

    setExtracting(true);
    setError(null);
    setExtractResult(null);
    setDecryptResult(null);

    try {
      const result = await extractFromImage(stegoFile, 'base64');
      setExtractResult(result);
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
      setError('Extract the envelope from the image first.');
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
        ...(decryptMode === 'password' ? { password: passwordInput.trim(), salt: saltInput.trim() } : {}),
      };

      const result = await decryptMessage(decReq);
      setDecryptResult(result);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Decryption failed.';
      setError(`Authentication Failure: ${msg}`);
    } finally {
      setDecrypting(false);
    }
  };

  const copyPlaintextToClipboard = () => {
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
              <span className="font-mono text-xs text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">
                Phase 3 Verified
              </span>
              <h1 className="text-base font-bold text-canvas-textPrimary tracking-tight">
                Receiver: Extraction & Authenticated Decryption
              </h1>
            </div>
            <p className="text-xs text-canvas-textMuted mt-1">
              Extract the length-prefixed steganographic payload from a carrier PNG, verify CRC32 framing, and decrypt using authenticated AES-256-GCM.
            </p>
          </div>
        </div>

        {error && (
          <div className="mt-4 border border-rose-900/60 bg-rose-950/20 rounded p-3 text-xs text-rose-300 flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* 2-Step Extraction & Decryption Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Step 1: Upload Stego Carrier & Extract */}
        <div className="border border-canvas-border bg-canvas-surface rounded-lg p-5 space-y-4">
          <div className="flex items-center space-x-2 text-xs font-mono text-canvas-textPrimary font-semibold pb-2 border-b border-canvas-border">
            <Upload className="w-3.5 h-3.5 text-accent" />
            <span>1. Upload Stego PNG Carrier</span>
          </div>

          <div>
            <label className="border border-dashed border-canvas-border hover:border-zinc-600 bg-canvas-base rounded-md p-4 flex flex-col items-center justify-center cursor-pointer transition-colors">
              <Upload className="w-6 h-6 text-canvas-textMuted mb-1" />
              <span className="text-xs font-mono text-canvas-textSecondary">
                {stegoFile ? stegoFile.name : 'Select or drop stego PNG carrier here'}
              </span>
              <span className="text-[10px] font-mono text-zinc-500 mt-0.5">
                PNG format required
              </span>
              <input
                type="file"
                accept="image/png"
                onChange={handleFileChange}
                className="hidden"
              />
            </label>
          </div>

          {stegoPreview && (
            <div className="flex items-center space-x-3 p-3 rounded bg-canvas-elevated border border-canvas-border text-xs font-mono">
              <img
                src={stegoPreview}
                alt="Carrier Preview"
                className="w-16 h-16 object-contain bg-zinc-950 rounded border border-canvas-border"
              />
              <div className="space-y-1">
                <div className="text-canvas-textPrimary">{stegoFile?.name}</div>
                <div className="text-canvas-textMuted text-[11px]">
                  {stegoFile ? (stegoFile.size / 1024).toFixed(1) : 0} KB
                </div>
              </div>
            </div>
          )}

          <button
            onClick={handleExtract}
            disabled={extracting || !stegoFile}
            className="w-full py-2.5 px-4 rounded bg-canvas-elevated hover:bg-zinc-800 disabled:opacity-40 border border-canvas-border text-canvas-textPrimary font-mono text-xs font-semibold flex items-center justify-center space-x-2 transition-colors cursor-pointer disabled:cursor-not-allowed"
          >
            {extracting ? (
              <span>Extracting LSB Channels...</span>
            ) : (
              <>
                <span>Extract Embedded Envelope</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>

          {/* Extraction Confirmation */}
          {extractResult && (
            <div className="p-3 rounded bg-emerald-950/20 border border-emerald-900/50 text-xs font-mono space-y-2">
              <div className="flex items-center space-x-1.5 text-emerald-400 font-semibold">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>LSB Framing Signature & CRC32 Verified</span>
              </div>
              <div className="text-[11px] text-zinc-300 space-y-1">
                <div className="flex justify-between">
                  <span className="text-canvas-textMuted">Extracted Envelope:</span>
                  <span>{extractResult.envelope_bytes_length} bytes</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-canvas-textMuted">Envelope Format:</span>
                  <span>Version {extractResult.envelope_version} (AES-256-GCM)</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Step 2: Decrypt & Authenticate */}
        <div className="border border-canvas-border bg-canvas-surface rounded-lg p-5 space-y-4">
          <div className="flex items-center space-x-2 text-xs font-mono text-canvas-textPrimary font-semibold pb-2 border-b border-canvas-border">
            <Key className="w-3.5 h-3.5 text-accent" />
            <span>2. Key Input & Authenticated Decryption</span>
          </div>

          <div>
            <label className="block text-xs font-mono text-canvas-textMuted mb-1.5">
              Decryption Method:
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
                AES Key (Base64)
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
                32-Byte AES-256 Key (Base64):
              </label>
              <input
                type="text"
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                placeholder="Paste key from Sender (e.g. kxOFT9apH+J7RENU9pE/GqIWC1IK7RcTA/9LrxTTw/s=)"
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
                  placeholder="Enter passphrase..."
                  className="w-full text-xs font-mono p-2 rounded bg-canvas-base border border-canvas-border text-canvas-textPrimary focus:outline-none focus:border-accent"
                />
              </div>
              <div>
                <label className="block text-xs font-mono text-canvas-textMuted mb-1">
                  16-Byte Salt (Base64):
                </label>
                <input
                  type="text"
                  value={saltInput}
                  onChange={(e) => setSaltInput(e.target.value)}
                  placeholder="Paste salt from Sender..."
                  className="w-full text-xs font-mono p-2 rounded bg-canvas-base border border-canvas-border text-canvas-textPrimary focus:outline-none focus:border-accent"
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
              <span>Verifying Authentication Tag...</span>
            ) : (
              <>
                <Unlock className="w-3.5 h-3.5" />
                <span>Authenticate & Decrypt Payload</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Recovered Secret Plaintext Result */}
      {decryptResult && (
        <div className="border border-emerald-900/60 bg-emerald-950/10 rounded-lg p-5 sm:p-6 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/40">
            <div className="flex items-center space-x-2 text-emerald-400 font-mono text-sm font-semibold">
              <ShieldCheck className="w-4 h-4" />
              <span>Decryption Authenticated (AES-256-GCM Tag Match)</span>
            </div>
            <span className="text-xs font-mono text-zinc-400">
              Recovered: {decryptResult.plaintext_bytes_length} bytes
            </span>
          </div>

          <div>
            <div className="flex items-center justify-between text-xs font-mono text-canvas-textMuted mb-1.5">
              <span>Recovered Plaintext Message:</span>
              <button
                onClick={copyPlaintextToClipboard}
                className="hover:text-canvas-textPrimary inline-flex items-center space-x-1"
                title="Copy Plaintext"
              >
                {copiedPlaintext ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copiedPlaintext ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <div className="bg-canvas-base p-4 rounded-md border border-canvas-border font-mono text-xs text-canvas-textPrimary whitespace-pre-wrap leading-relaxed select-all">
              {decryptResult.plaintext}
            </div>
          </div>

          <p className="text-[11px] font-mono text-zinc-500">
            Cryptographic guarantee: The message above was released only after AES-GCM mathematically verified that the ciphertext and envelope metadata were untampered.
          </p>
        </div>
      )}
    </div>
  );
};
