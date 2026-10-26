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

// ---------------------------------------------------------
// Video Steganography Types (Phase 5)
// ---------------------------------------------------------

export interface VideoCapacityResponse {
  width: number;
  height: number;
  channels_per_frame: number;
  num_frames: number;
  fps: number;
  duration_seconds: number;
  total_carrier_bits: number;
  total_carrier_bytes: number;
  header_overhead_bytes: number;
  max_usable_payload_bytes: number;
  recommended_codec: string;
  container_format: string;
}

export interface VideoQualityMetrics {
  average_mse: number;
  average_psnr: number | string;
  psnr_display: string;
  total_frames: number;
  modified_frames: number;
  embedded_bytes: number;
  framed_bytes: number;
  capacity_used_ratio: number;
  width: number;
  height: number;
  fps: number;
  duration_seconds: number;
}

export interface VideoEmbedResponse {
  stego_video_data_url: string;
  preview_frame_data_url: string;
  filename: string;
  embedded_bytes: number;
  metrics: VideoQualityMetrics;
  message: string;
}

export interface VideoExtractResponse {
  envelope: string;
  encoding: 'base64' | 'hex';
  envelope_bytes_length: number;
  envelope_version: number;
  status: 'verified';
  message: string;
}

// ---------------------------------------------------------
// Multimodal Allocation & Orchestration Types (Phase 6)
// ---------------------------------------------------------

export interface ImageProfile {
  carrier_type: 'image';
  width: number;
  height: number;
  channels: number;
  color_mode: string;
  total_carrier_bytes: number;
  header_overhead_bytes: number;
  max_usable_payload_bytes: number;
  laplacian_variance: number;
  mean_intensity: number;
  std_intensity: number;
  edge_density: number;
  complexity_score: number;
}

export interface AudioProfile {
  carrier_type: 'audio';
  sample_rate: number;
  bits_per_sample: number;
  num_channels: number;
  channel_layout: string;
  total_samples: number;
  duration_seconds: number;
  total_carrier_bytes: number;
  header_overhead_bytes: number;
  max_usable_payload_bytes: number;
  rms_energy: number;
  sample_diff_variance: number;
  mean_abs_diff: number;
  complexity_score: number;
}

export interface VideoProfile {
  carrier_type: 'video';
  width: number;
  height: number;
  num_frames: number;
  fps: number;
  duration_seconds: number;
  recommended_codec: string;
  container_format: string;
  total_carrier_bytes: number;
  header_overhead_bytes: number;
  max_usable_payload_bytes: number;
  frame_diff_variance: number;
  keyframe_laplacian_variance: number;
  complexity_score: number;
}

export interface MultimodalAnalyzeResponse {
  image: ImageProfile;
  audio: AudioProfile;
  video: VideoProfile;
  total_usable_capacity_bytes: number;
  capacity_shares: Record<string, number>;
  simulated_allocation?: Record<string, any>;
  message: string;
}

export interface CarrierAllocationOutcome {
  carrier_type: string;
  payload_bytes: number;
  chunk_overhead_bytes: number;
  total_carrier_payload_bytes: number;
  carrier_usable_capacity_bytes: number;
  carrier_net_capacity_bytes: number;
  utilization_ratio: number;
  complexity_score: number;
  weight: number;
  reason: string;
}

export interface MultimodalEmbedResponse {
  zip_bundle_data_url: string;
  filename: string;
  key: string;
  key_encoding: 'base64' | 'hex';
  salt: string | null;
  message_id: string;
  strategy: string;
  total_envelope_bytes: number;
  total_usable_capacity_bytes: number;
  overall_utilization_ratio: number;
  allocations: Record<string, CarrierAllocationOutcome>;
  metrics: {
    image: { psnr_display: string; mse: number; ssim: number };
    audio: { snr_display: string; mse: number };
    video: { psnr_display: string; average_mse: number };
  };
  preview_frame_data_url: string;
  manifest: Record<string, any>;
  message: string;
}

export interface MultimodalExtractResponse {
  plaintext: string;
  message_id: string;
  envelope_bytes_length: number;
  chunk_count: number;
  chunk_sizes: Record<string, number>;
  verified: boolean;
  manifest?: Record<string, any>;
  message: string;
}

// ---------------------------------------------------------
// Steganalysis & Detectability Types (Phase 7)
// ---------------------------------------------------------

export interface SteganalysisMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  roc_auc: number | null;
  true_positives: number;
  true_negatives: number;
  false_positives: number;
  false_negatives: number;
  total_samples: number;
  cover_count: number;
  stego_count: number;
  by_payload_category: Record<string, { sample_count: number; stego_detection_rate: number }>;
  by_allocation_strategy: Record<string, { sample_count: number; stego_detection_rate: number }>;
  limitations_note: string;
  is_calibrated?: boolean;
  calibration_method?: string;
}

export interface SteganalysisDatasetSummary {
  modality: 'image' | 'audio' | 'video';
  total_samples: number;
  cover_count: number;
  stego_count: number;
  sources_count: number;
  feature_count: number;
  feature_names: string[];
}

export interface SteganalysisTrainRequest {
  modality: 'all' | 'image' | 'audio' | 'video';
  model_type: 'random_forest' | 'logistic_regression';
  num_sources: number;
}

export interface SteganalysisTrainResponse {
  modality: string;
  model_type: string;
  train_sources_count: number;
  test_sources_count: number;
  training_metrics: SteganalysisMetrics;
  test_metrics: SteganalysisMetrics;
  trained_at: string;
  message: string;
}

export interface SteganalysisClassifyResponse {
  modality: string;
  filename: string;
  predicted_label: number;
  predicted_class: 'Cover' | 'Stego';
  stego_probability: number;
  confidence_percentage: number;
  model_type: string;
  feature_values: Record<string, number>;
  disclaimer: string;
  is_calibrated?: boolean;
  calibration_method?: string;
}


