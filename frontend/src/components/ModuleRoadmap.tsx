import React from 'react';
import { ModuleStatus } from '../api/types';
import { StatusBadge } from './StatusBadge';

interface ModuleRoadmapProps {
  modules: Record<string, ModuleStatus> | undefined;
  loading: boolean;
}

export const ModuleRoadmap: React.FC<ModuleRoadmapProps> = ({ modules, loading }) => {
  return (
    <section className="border border-canvas-border bg-canvas-surface rounded-lg p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-canvas-border">
        <div>
          <h2 className="text-sm font-semibold text-canvas-textPrimary tracking-tight">
            Backend Research Engine Modules
          </h2>
          <p className="text-xs text-canvas-textMuted">
            Real-time module lifecycle reporting queried directly from <code className="font-mono text-zinc-300">/api/status</code>.
          </p>
        </div>

        {modules && (
          <div className="flex items-center space-x-2 text-xs font-mono text-canvas-textMuted">
            <span>Verified Active:</span>
            <span className="text-emerald-400 font-semibold">
              {Object.values(modules).filter(m => m.status === 'implemented').length}
            </span>
            <span>/</span>
            <span>{Object.values(modules).length} Total Modules</span>
          </div>
        )}
      </div>

      {/* Clean Table Layout */}
      <div className="overflow-x-auto border border-canvas-border rounded-md">
        <table className="w-full text-left text-xs border-collapse">
          <thead className="bg-canvas-elevated font-mono uppercase tracking-wider text-[11px] text-canvas-textMuted border-b border-canvas-border">
            <tr>
              <th scope="col" className="px-4 py-3 font-semibold">Research Module</th>
              <th scope="col" className="px-4 py-3 font-semibold">Target Phase</th>
              <th scope="col" className="px-4 py-3 font-semibold">Implementation State</th>
              <th scope="col" className="px-4 py-3 font-semibold">Scope & Deliverables</th>
              <th scope="col" className="px-4 py-3 font-semibold">Capabilities</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-canvas-borderSubtle bg-canvas-surface font-sans text-canvas-textSecondary">
            {modules ? (
              Object.entries(modules).map(([key, module]) => {
                const isImplemented = module.status === 'implemented';

                return (
                  <tr 
                    key={key} 
                    className={`hover:bg-canvas-elevated/40 transition-colors ${
                      isImplemented ? 'bg-emerald-950/5' : ''
                    }`}
                  >
                    <td className="px-4 py-3.5 font-medium text-canvas-textPrimary whitespace-nowrap">
                      <div className="flex items-center space-x-2">
                        <span className={`w-1.5 h-1.5 rounded-full ${isImplemented ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
                        <span>{module.name}</span>
                      </div>
                    </td>

                    <td className="px-4 py-3.5 font-mono text-[11px] text-canvas-textMuted whitespace-nowrap">
                      Phase {module.phase}
                    </td>

                    <td className="px-4 py-3.5 whitespace-nowrap">
                      <StatusBadge 
                        status={module.status} 
                        label={isImplemented ? "Implemented & Tested" : "Planned (Pending)"}
                      />
                    </td>

                    <td className="px-4 py-3.5 text-xs text-canvas-textSecondary max-w-sm">
                      {module.description}
                    </td>

                    <td className="px-4 py-3.5">
                      {module.capabilities && module.capabilities.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {module.capabilities.map((cap, idx) => (
                            <span 
                              key={idx} 
                              className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700"
                            >
                              {cap}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="font-mono text-[11px] text-zinc-600 italic">—</span>
                      )}
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-zinc-500 font-mono text-xs">
                  {loading ? 'Retrieving module roadmap from backend...' : 'No status data received.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
};
