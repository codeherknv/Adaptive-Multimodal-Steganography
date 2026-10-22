export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  timestamp: string;
}

export interface ModuleStatus {
  name: string;
  phase: number;
  status: 'implemented' | 'in_progress' | 'pending';
  description: string;
  capabilities: string[];
}

export interface SystemStatusResponse {
  project_name: string;
  version: string;
  current_phase: number;
  modules: Record<string, ModuleStatus>;
}

// ---------------------------------------------------------
// Crypto Types (Phase 2)
// ---------------------------------------------------------

export interface EncryptRequest {
  plaintext: string;
  key?: string;
  password?: string;
  salt?: string;
  encoding?: 'base64' | 'hex';
}

export interface EncryptResponse {
  key: string;
  key_encoding: 'base64' | 'hex';
  salt: string | null;
  envelope_version: number;
  nonce: string;
  ciphertext: string;
  envelope: string;
  envelope_bytes_length: number;
  plaintext_bytes_length: number;
  warning: string;
}

export interface DecryptRequest {
  envelope: string;
  key?: string;
  password?: string;
  salt?: string;
  encoding?: 'base64' | 'hex';
}

export interface DecryptResponse {
  plaintext: string;
  authenticated: boolean;
  envelope_version: number;
  plaintext_bytes_length: number;
}

// ---------------------------------------------------------
// Image Steganography Types (Phase 3)
// ---------------------------------------------------------

export interface ImageCapacityResponse {
  width: number;
  height: number;
  channels: number;
  color_mode: string;
  embeddable_channels_per_pixel: number;
  total_carrier_bits: number;
  total_carrier_bytes: number;
  header_overhead_bytes: number;
  max_usable_payload_bytes: number;
}

export interface ImageQualityMetrics {
  mse: number;
  psnr: number | string;
  psnr_display: string;
  ssim: number;
  embedded_bytes: number;
  framed_bytes: number;
  capacity_used_ratio: number;
  bits_per_pixel: number;
}

export interface ImageEmbedResponse {
  stego_image_data_url: string;
  filename: string;
  embedded_bytes: number;
  metrics: ImageQualityMetrics;
  message: string;
}

export interface ImageExtractResponse {
  envelope: string;
  encoding: 'base64' | 'hex';
  envelope_bytes_length: number;
  envelope_version: number;
  status: 'verified';
  message: string;
}

// ---------------------------------------------------------
// Audio Steganography Types (Phase 4)
// ---------------------------------------------------------

export interface AudioCapacityResponse {
  num_channels: number;
  channel_layout: string;
  sample_rate: number;
  sample_width: number;
  bits_per_sample: number;
  num_frames: number;
  duration_seconds: number;
  total_samples: number;
  total_carrier_bits: number;
  total_carrier_bytes: number;
  header_overhead_bytes: number;
  max_usable_payload_bytes: number;
}

export interface AudioQualityMetrics {
  mse: number;
  snr: number | string;
  snr_display: string;
  embedded_bytes: number;
  framed_bytes: number;
  capacity_used_ratio: number;
  bits_per_sample_used: number;
}

export interface AudioEmbedResponse {
  stego_audio_data_url: string;
  filename: string;
  embedded_bytes: number;
  metrics: AudioQualityMetrics;
  message: string;
}

export interface AudioExtractResponse {
  envelope: string;
  encoding: 'base64' | 'hex';
  envelope_bytes_length: number;
  envelope_version: number;
  status: 'verified';
  message: string;
}
