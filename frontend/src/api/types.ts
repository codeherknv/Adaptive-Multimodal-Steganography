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
