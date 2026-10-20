import axios from 'axios';
import { HealthResponse, SystemStatusResponse } from './types';

// Use environment variable if provided, otherwise default to relative '/api' proxied by Vite
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const checkHealth = async (): Promise<HealthResponse> => {
  const response = await apiClient.get<HealthResponse>('/health');
  return response.data;
};

export const getSystemStatus = async (): Promise<SystemStatusResponse> => {
  const response = await apiClient.get<SystemStatusResponse>('/status');
  return response.data;
};
