import axios from 'axios';
import { 
  HealthResponse, 
  SystemStatusResponse,
  EncryptRequest,
  EncryptResponse,
  DecryptRequest,
  DecryptResponse,
  ImageCapacityResponse,
  ImageEmbedResponse,
  ImageExtractResponse,
  AudioCapacityResponse,
  AudioEmbedResponse,
  AudioExtractResponse,
  VideoCapacityResponse,
  VideoEmbedResponse,
  VideoExtractResponse,
  MultimodalAnalyzeResponse,
  MultimodalEmbedResponse,
  MultimodalExtractResponse,
  SteganalysisDatasetSummary,
  SteganalysisTrainRequest,
  SteganalysisTrainResponse,
  SteganalysisClassifyResponse,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

export const checkHealth = async (): Promise<HealthResponse> => {
  const response = await apiClient.get<HealthResponse>('/health');
  return response.data;
};

export const getSystemStatus = async (): Promise<SystemStatusResponse> => {
  const response = await apiClient.get<SystemStatusResponse>('/status');
  return response.data;
};

// ---------------------------------------------------------
// Crypto API (Phase 2)
// ---------------------------------------------------------

export const encryptMessage = async (data: EncryptRequest): Promise<EncryptResponse> => {
  const response = await apiClient.post<EncryptResponse>('/crypto/encrypt', data);
  return response.data;
};

export const decryptMessage = async (data: DecryptRequest): Promise<DecryptResponse> => {
  const response = await apiClient.post<DecryptResponse>('/crypto/decrypt', data);
  return response.data;
};

// ---------------------------------------------------------
// Image Steganography API (Phase 3)
// ---------------------------------------------------------

export const checkImageCapacity = async (file: File): Promise<ImageCapacityResponse> => {
  const formData = new FormData();
  formData.append('image', file);
  const response = await apiClient.post<ImageCapacityResponse>('/image/capacity', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const embedInImage = async (
  file: File, 
  envelope: string, 
  encoding: 'base64' | 'hex' = 'base64'
): Promise<ImageEmbedResponse> => {
  const formData = new FormData();
  formData.append('image', file);
  formData.append('envelope', envelope);
  formData.append('encoding', encoding);
  const response = await apiClient.post<ImageEmbedResponse>('/image/embed', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const extractFromImage = async (
  file: File, 
  encoding: 'base64' | 'hex' = 'base64'
): Promise<ImageExtractResponse> => {
  const formData = new FormData();
  formData.append('image', file);
  formData.append('encoding', encoding);
  const response = await apiClient.post<ImageExtractResponse>('/image/extract', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

// ---------------------------------------------------------
// Audio Steganography API (Phase 4)
// ---------------------------------------------------------

export const checkAudioCapacity = async (file: File): Promise<AudioCapacityResponse> => {
  const formData = new FormData();
  formData.append('audio', file);
  const response = await apiClient.post<AudioCapacityResponse>('/audio/capacity', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const embedInAudio = async (
  file: File,
  envelope: string,
  encoding: 'base64' | 'hex' = 'base64'
): Promise<AudioEmbedResponse> => {
  const formData = new FormData();
  formData.append('audio', file);
  formData.append('envelope', envelope);
  formData.append('encoding', encoding);
  const response = await apiClient.post<AudioEmbedResponse>('/audio/embed', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const extractFromAudio = async (
  file: File,
  encoding: 'base64' | 'hex' = 'base64'
): Promise<AudioExtractResponse> => {
  const formData = new FormData();
  formData.append('audio', file);
  formData.append('encoding', encoding);
  const response = await apiClient.post<AudioExtractResponse>('/audio/extract', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

// ---------------------------------------------------------
// Video Steganography API (Phase 5)
// ---------------------------------------------------------

export const checkVideoCapacity = async (file: File): Promise<VideoCapacityResponse> => {
  const formData = new FormData();
  formData.append('video', file);
  const response = await apiClient.post<VideoCapacityResponse>('/video/capacity', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const embedInVideo = async (
  file: File,
  envelope: string,
  encoding: 'base64' | 'hex' = 'base64'
): Promise<VideoEmbedResponse> => {
  const formData = new FormData();
  formData.append('video', file);
  formData.append('envelope', envelope);
  formData.append('encoding', encoding);
  const response = await apiClient.post<VideoEmbedResponse>('/video/embed', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const extractFromVideo = async (
  file: File,
  encoding: 'base64' | 'hex' = 'base64'
): Promise<VideoExtractResponse> => {
  const formData = new FormData();
  formData.append('video', file);
  formData.append('encoding', encoding);
  const response = await apiClient.post<VideoExtractResponse>('/video/extract', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

// ---------------------------------------------------------
// Multimodal Allocation & Orchestration API (Phase 6)
// ---------------------------------------------------------

export const analyzeMultimodalTriad = async (
  formData: FormData
): Promise<MultimodalAnalyzeResponse> => {
  const response = await apiClient.post<MultimodalAnalyzeResponse>('/multimodal/analyze', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const embedMultimodal = async (
  formData: FormData
): Promise<MultimodalEmbedResponse> => {
  const response = await apiClient.post<MultimodalEmbedResponse>('/multimodal/embed', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const extractMultimodal = async (
  formData: FormData
): Promise<MultimodalExtractResponse> => {
  const response = await apiClient.post<MultimodalExtractResponse>('/multimodal/extract', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

// ---------------------------------------------------------
// ML Steganalysis API (Phase 7)
// ---------------------------------------------------------

export const generateSteganalysisDataset = async (
  req: SteganalysisTrainRequest
): Promise<SteganalysisDatasetSummary[]> => {
  const response = await apiClient.post<SteganalysisDatasetSummary[]>('/steganalysis/dataset/generate', req);
  return response.data;
};

export const getSteganalysisDatasetSummary = async (): Promise<SteganalysisDatasetSummary[]> => {
  const response = await apiClient.get<SteganalysisDatasetSummary[]>('/steganalysis/dataset/summary');
  return response.data;
};

export const trainSteganalyzers = async (
  req: SteganalysisTrainRequest
): Promise<SteganalysisTrainResponse[]> => {
  const response = await apiClient.post<SteganalysisTrainResponse[]>('/steganalysis/train', req);
  return response.data;
};

export const listTrainedSteganalyzers = async (): Promise<SteganalysisTrainResponse[]> => {
  const response = await apiClient.get<SteganalysisTrainResponse[]>('/steganalysis/models');
  return response.data;
};

export const classifyMediaFile = async (
  formData: FormData
): Promise<SteganalysisClassifyResponse> => {
  const response = await apiClient.post<SteganalysisClassifyResponse>('/steganalysis/classify', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};


