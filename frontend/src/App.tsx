import React, { useEffect, useState } from 'react';
import { 
  ShieldCheck, 
  Server, 
  RefreshCw, 
  CheckCircle2, 
  Clock, 
  AlertTriangle,
  Layers,
  Cpu,
  FileCode2
} from 'lucide-react';
import { checkHealth, getSystemStatus } from './api/client';
import { HealthResponse, SystemStatusResponse } from './api/types';
import { StatusBadge } from './components/StatusBadge';

export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastCheck, setLastCheck] = useState<Date | null>(null);

  const fetchStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthData, statusData] = await Promise.all([
        checkHealth(),
        getSystemStatus()
      ]);
      setHealth(healthData);
      setStatus(statusData);
      setLastCheck(new Date());
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to connect to backend API server.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0d14] text-slate-200">
      {/* Top Navbar */}
      <header className="border-b border-slate-800 bg-[#0d121d]/90 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-cyan-950 border border-cyan-800 flex items-center justify-center text-cyan-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <span className="text-sm font-semibold tracking-wider uppercase text-cyan-400">Cybersecurity Research</span>
              <h1 className="text-base font-bold text-slate-100 leading-tight">Adaptive Multimodal Steganography</h1>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 text-xs">
              <span className="text-slate-400">API Gateway:</span>
              {health ? (
                <StatusBadge status={health.status} />
              ) : (
                <span className="text-slate-500">Checking...</span>
              )}
            </div>
            <button
              onClick={fetchStatus}
              disabled={loading}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>Ping Backend</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Hero Section */}
        <div className="rounded-xl border border-slate-800 bg-gradient-to-br from-[#0f172a] to-[#0b1120] p-6 lg:p-8">
          <div className="max-w-3xl">
            <div className="inline-flex items-center space-x-2 px-2.5 py-1 rounded-full text-xs font-medium bg-cyan-950/80 text-cyan-300 border border-cyan-800/60 mb-4">
              <span>Phase 1 Verified</span>
              <span>•</span>
              <span>Monorepo & Environment Baseline</span>
            </div>
            <h2 className="text-2xl lg:text-3xl font-extrabold text-white tracking-tight">
              Reliability-Aware Adaptive Multimodal Steganography
            </h2>
            <p className="mt-2 text-sm text-slate-400 leading-relaxed">
              An academic research platform evaluating empirical payload allocation policies across 
              image, audio, and video carriers with baseline machine-learning steganalysis.
            </p>
          </div>

          <div className="mt-6 pt-6 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-[#0a0f1d] rounded-lg p-3.5 border border-slate-800">
              <div className="text-xs text-slate-400 flex items-center space-x-1.5">
                <Server className="w-3.5 h-3.5 text-cyan-400" />
                <span>Backend Framework</span>
              </div>
              <div className="mt-1 text-sm font-semibold text-slate-200">FastAPI + Python 3.13</div>
            </div>

            <div className="bg-[#0a0f1d] rounded-lg p-3.5 border border-slate-800">
              <div className="text-xs text-slate-400 flex items-center space-x-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                <span>Frontend Stack</span>
              </div>
              <div className="mt-1 text-sm font-semibold text-slate-200">React 18 + Vite + TypeScript</div>
            </div>

            <div className="bg-[#0a0f1d] rounded-lg p-3.5 border border-slate-800">
              <div className="text-xs text-slate-400 flex items-center space-x-1.5">
                <Cpu className="w-3.5 h-3.5 text-cyan-400" />
                <span>Current Phase</span>
              </div>
              <div className="mt-1 text-sm font-semibold text-emerald-400">
                Phase 1: Foundation Complete
              </div>
            </div>

            <div className="bg-[#0a0f1d] rounded-lg p-3.5 border border-slate-800">
              <div className="text-xs text-slate-400 flex items-center space-x-1.5">
                <Clock className="w-3.5 h-3.5 text-cyan-400" />
                <span>API Link Status</span>
              </div>
              <div className="mt-1 text-sm font-semibold text-slate-200">
                {lastCheck ? lastCheck.toLocaleTimeString() : 'Awaiting sync'}
              </div>
            </div>
          </div>
        </div>

        {/* Live Diagnostics Card */}
        {error && (
          <div className="rounded-lg border border-red-900/60 bg-red-950/30 p-4 text-sm text-red-300 flex items-start space-x-3">
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-red-200">API Connection Offline</p>
              <p className="mt-1 text-xs text-red-300/80">
                Ensure the FastAPI backend is running on <code className="bg-red-950 px-1 py-0.5 rounded">http://127.0.0.1:8000</code>.
                Error details: {error}
              </p>
            </div>
          </div>
        )}

        {/* Module Implementation Status */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-white">Module Implementation State</h3>
              <p className="text-xs text-slate-400">
                Truthful reporting directly from backend route <code className="text-cyan-400 bg-slate-900 px-1 py-0.5 rounded">/api/status</code>.
              </p>
            </div>
            {status && (
              <span className="text-xs text-slate-400">
                {Object.values(status.modules).filter(m => m.status === 'implemented').length} of {Object.values(status.modules).length} modules active
              </span>
            )}
          </div>

          <div className="rounded-xl border border-slate-800 bg-[#0d1322] overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-[#11192d] text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800">
                  <tr>
                    <th scope="col" className="px-6 py-3.5">Module Name</th>
                    <th scope="col" className="px-6 py-3.5">Target Phase</th>
                    <th scope="col" className="px-6 py-3.5">Status</th>
                    <th scope="col" className="px-6 py-3.5">Description</th>
                    <th scope="col" className="px-6 py-3.5">Active Capabilities</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70 text-slate-300">
                  {status ? (
                    Object.entries(status.modules).map(([key, module]) => (
                      <tr key={key} className="hover:bg-slate-800/30 transition-colors">
                        <td className="px-6 py-4 font-medium text-slate-200">
                          {module.name}
                        </td>
                        <td className="px-6 py-4 text-xs font-mono text-slate-400">
                          Phase {module.phase}
                        </td>
                        <td className="px-6 py-4">
                          <StatusBadge status={module.status} />
                        </td>
                        <td className="px-6 py-4 text-xs text-slate-400 max-w-md">
                          {module.description}
                        </td>
                        <td className="px-6 py-4 text-xs">
                          {module.capabilities.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {module.capabilities.map((cap, i) => (
                                <span 
                                  key={i} 
                                  className="inline-flex items-center px-2 py-0.5 rounded text-[11px] bg-slate-800 text-cyan-300 border border-slate-700"
                                >
                                  {cap}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-500 italic">Planned</span>
                          )}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                        {loading ? 'Retrieving backend module status...' : 'No status data available.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Phase 1 Verification Guide for the Student */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="rounded-xl border border-slate-800 bg-[#0d1322] p-5 space-y-3">
            <div className="flex items-center space-x-2 text-cyan-400 font-semibold text-sm">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Phase 1 Verification Checklist</span>
            </div>
            <ul className="text-xs text-slate-400 space-y-2">
              <li className="flex items-start space-x-2">
                <span className="text-emerald-400 font-bold">✓</span>
                <span>Python 3.13 venv configured with all pinned dependencies installed.</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-emerald-400 font-bold">✓</span>
                <span>FastAPI backend initialized with <code className="text-cyan-300">/api/health</code> and <code className="text-cyan-300">/api/status</code>.</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-emerald-400 font-bold">✓</span>
                <span>Automated pytest suite passing (3 unit tests verified).</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-emerald-400 font-bold">✓</span>
                <span>Vite + React + TypeScript + Tailwind CSS configured with proxy routing.</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-emerald-400 font-bold">✓</span>
                <span>Clean directory structure with documentation, data, output, and results directories.</span>
              </li>
            </ul>
          </div>

          <div className="rounded-xl border border-slate-800 bg-[#0d1322] p-5 space-y-3">
            <div className="flex items-center space-x-2 text-cyan-400 font-semibold text-sm">
              <FileCode2 className="w-4 h-4" />
              <span>Quick Development Commands</span>
            </div>
            <div className="space-y-2 text-xs">
              <div>
                <p className="text-slate-400 mb-1 font-mono text-[11px]"># Run Backend Server (from /backend):</p>
                <div className="bg-[#070a10] p-2 rounded border border-slate-800 font-mono text-cyan-300 select-all">
                  .\venv\Scripts\Activate.ps1; python -m uvicorn app.main:app --reload --port 8000
                </div>
              </div>
              <div className="pt-1">
                <p className="text-slate-400 mb-1 font-mono text-[11px]"># Run Frontend Dev Server (from /frontend):</p>
                <div className="bg-[#070a10] p-2 rounded border border-slate-800 font-mono text-cyan-300 select-all">
                  npm run dev
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;
