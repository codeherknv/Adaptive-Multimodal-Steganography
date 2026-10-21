import React, { useState } from 'react';
import { 
  Lock, 
  Upload, 
  Image as ImageIcon, 
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
  encryptMessage, 
  embedInImage 
} from '../api/client';
import { 
  ImageCapacityResponse, 
  ImageEmbedResponse, 
  EncryptResponse 
} from '../api/types';

export const Sender: React.FC = () => {
  // Input states
  const [plaintext, setPlaintext] = useState<string>('Top Secret Multimodal Research Payload: 33/33/34 allocation baseline.');
  const [keyMode, setKeyMode] = useState<'auto' | 'custom' | 'password'>('auto');
  const [customKey, setCustomKey] = useState<string>('');
  const [password, setPassword] = useState<string>('');

  // Carrier file states
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
  const [capacity, setCapacity] = useState<ImageCapacityResponse | null>(null);
  const [capacityLoading, setCapacityLoading] = useState<boolean>(false);

  // Execution states
  const [processing, setProcessing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [encryptResult, setEncryptResult] = useState<EncryptResponse | null>(null);
  const [embedResult, setEmbedResult] = useState<ImageEmbedResponse | null>(null);

  // Clipboard copy feedback
  const [copiedKey, setCopiedKey] = useState<boolean>(false);

  // Handle Cover PNG selection
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setEmbedResult(null);
    setEncryptResult(null);

    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.png') && file.type !== 'image/png') {
      setError('Please select a lossless PNG image. JPEG and lossy formats destroy LSB data.');
      return;
    }

    setCoverFile(file);
    const reader = new FileReader();
    reader.onload = () => setCoverPreview(reader.result as string);
    reader.readAsDataURL(file);

    // Query backend capacity
    setCapacityLoading(true);
    try {
      const capData = await checkImageCapacity(file);
      setCapacity(capData);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(`Failed to inspect carrier image: ${err.message}`);
      } else {
        setError('Failed to calculate carrier capacity.');
      }
      setCapacity(null);
    } finally {
      setCapacityLoading(false);
    }
  };

  // Execute full Encrypt + Embed Pipeline
  const handleEncryptAndEmbed = async () => {
    if (!plaintext.trim()) {
      setError('Please enter a secret message to encrypt.');
      return;
    }
    if (!coverFile) {
      setError('Please select a PNG cover image carrier.');
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

      // Step 2: Embed encrypted envelope into PNG carrier via Phase 3 endpoint
      const embedResponse = await embedInImage(
        coverFile,
        encResponse.envelope,
        'base64'
      );
      setEmbedResult(embedResponse);
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
                Phase 3 Verified
              </span>
              <h1 className="text-base font-bold text-canvas-textPrimary tracking-tight">
                Sender: Lossless PNG Image Steganography
              </h1>
            </div>
            <p className="text-xs text-canvas-textMuted mt-1">
              Encrypt secret plaintext with authenticated AES-256-GCM and embed the envelope into PNG pixels using spatial LSB.
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

        {/* Right Column: PNG Carrier & Capacity */}
        <div className="border border-canvas-border bg-canvas-surface rounded-lg p-5 space-y-4">
          <div className="flex items-center space-x-2 text-xs font-mono text-canvas-textPrimary font-semibold pb-2 border-b border-canvas-border">
            <ImageIcon className="w-3.5 h-3.5 text-accent" />
            <span>2. Cover Image Carrier & Capacity</span>
          </div>

          <div>
            <label className="block text-xs font-mono text-canvas-textMuted mb-1.5">
              Select Lossless Cover PNG:
            </label>
            <label className="border border-dashed border-canvas-border hover:border-zinc-600 bg-canvas-base rounded-md p-4 flex flex-col items-center justify-center cursor-pointer transition-colors">
              <Upload className="w-6 h-6 text-canvas-textMuted mb-1" />
              <span className="text-xs font-mono text-canvas-textSecondary">
                {coverFile ? coverFile.name : 'Click or drop a PNG image here'}
              </span>
              <span className="text-[10px] font-mono text-zinc-500 mt-0.5">
                PNG format required (Max 25 MB)
              </span>
              <input
                type="file"
                accept="image/png"
                onChange={handleFileChange}
                className="hidden"
              />
            </label>
          </div>

          {/* Carrier Preview & Capacity Info */}
          {coverPreview && (
            <div className="flex items-start space-x-4 p-3 rounded bg-canvas-elevated border border-canvas-border text-xs font-mono">
              <img
                src={coverPreview}
                alt="Cover Preview"
                className="w-20 h-20 object-contain bg-zinc-950 rounded border border-canvas-border shrink-0"
              />
              <div className="space-y-1 flex-1">
                <div className="flex justify-between">
                  <span className="text-canvas-textMuted">File Size:</span>
                  <span className="text-canvas-textPrimary">{coverFile ? (coverFile.size / 1024).toFixed(1) : 0} KB</span>
                </div>
                {capacity && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Resolution:</span>
                      <span className="text-canvas-textPrimary">{capacity.width} × {capacity.height} ({capacity.color_mode})</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Max Payload:</span>
                      <span className="text-emerald-400 font-semibold">{capacity.max_usable_payload_bytes.toLocaleString()} bytes</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-canvas-textMuted">Required:</span>
                      <span className={`${estimatedPayloadBytes > capacity.max_usable_payload_bytes ? 'text-rose-400 font-bold' : 'text-canvas-textPrimary'}`}>
                        {estimatedPayloadBytes} bytes
                      </span>
                    </div>
                  </>
                )}
                {capacityLoading && (
                  <span className="text-zinc-500 italic">Calculating carrier capacity...</span>
                )}
              </div>
            </div>
          )}

          {/* Action Button */}
          <button
            onClick={handleEncryptAndEmbed}
            disabled={processing || !coverFile || !plaintext.trim()}
            className="w-full py-2.5 px-4 rounded bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white font-mono text-xs font-semibold flex items-center justify-center space-x-2 transition-colors cursor-pointer disabled:cursor-not-allowed"
          >
            {processing ? (
              <span>Encrypting & Embedding LSB...</span>
            ) : (
              <>
                <span>Encrypt & Embed into PNG</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Results & Stego Download Section */}
      {embedResult && (
        <div className="border border-emerald-900/60 bg-emerald-950/10 rounded-lg p-5 sm:p-6 space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/40">
            <div className="flex items-center space-x-2 text-emerald-400 font-mono text-sm font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Steganographic Embedding Succeeded</span>
            </div>
            <span className="text-xs font-mono text-zinc-400">
              Payload: {embedResult.embedded_bytes} bytes concealed
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
                  src={embedResult.stego_image_data_url}
                  alt="Stego Output"
                  className="max-h-48 object-contain rounded"
                />
              </div>
              <a
                href={embedResult.stego_image_data_url}
                download={embedResult.filename}
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
                    {embedResult.metrics.psnr_display}
                  </span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Mean Squared Error (MSE):</span>
                  <span className="text-canvas-textPrimary">{embedResult.metrics.mse}</span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Structural Similarity (SSIM):</span>
                  <span className="text-canvas-textPrimary">{embedResult.metrics.ssim}</span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Bits Per Pixel (bpp):</span>
                  <span className="text-canvas-textPrimary">{embedResult.metrics.bits_per_pixel}</span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-canvas-textMuted">Carrier Capacity Used:</span>
                  <span className="text-canvas-textPrimary">{(embedResult.metrics.capacity_used_ratio * 100).toFixed(2)}%</span>
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
                  <strong>Academic Key Hygiene:</strong> This key is <em>never</em> embedded inside the image. You must provide it to the Receiver to authenticate and decrypt the recovered message.
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
