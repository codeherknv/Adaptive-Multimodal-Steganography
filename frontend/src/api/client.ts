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
