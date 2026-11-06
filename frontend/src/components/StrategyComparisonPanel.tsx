import React, { useState } from 'react';
import { 
  BarChart3, 
  AlertTriangle, 
  CheckCircle2, 
  Info, 
  RefreshCw, 
  ArrowRight
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  Legend, 
  Cell 
} from 'recharts';
import { MultimodalCompareResponse } from '../api/types';

interface StrategyComparisonPanelProps {
  imageFile: File | null;
  audioFile: File | null;
  videoFile: File | null;
  message: string;
  compareData: MultimodalCompareResponse | null;
  loading: boolean;
  error: string | null;
  onRunComparison: () => void;
  onSelectStrategy?: (stratKey: string, lambdaParam?: number) => void;
}

export const StrategyComparisonPanel: React.FC<StrategyComparisonPanelProps> = ({
  imageFile,
  audioFile,
  videoFile,
  message,
  compareData,
  loading,
  error,
  onRunComparison,
  onSelectStrategy,
}) => {
  const [chartView, setChartView] = useState<'risk' | 'shares'>('shares');

  const hasCarriers = Boolean(imageFile && audioFile && videoFile);

  // Prepare chart data from rows
  const chartData = compareData?.rows.map((row) => {
    const shortLabel = row.strategy_name.replace('Portfolio (Markowitz', 'Port.').replace('Adaptive Feature-Weighted', 'Adaptive').replace('Capacity-Proportional', 'Cap-Prop').replace('Square-Root-Law (Ker)', 'Sqrt-Law').replace('Random Key-Seeded (seed=42)', 'Random').replace('Max-Complexity Greedy', 'Greedy').replace('Minimax Risk', 'Minimax');
    return {
      name: shortLabel,
      fullName: row.strategy_name,
      isNovel: row.is_novel,
      riskProxy: row.modeled_risk_proxy ?? 0,
      imageShare: row.share_image_pct ?? 0,
      audioShare: row.share_audio_pct ?? 0,
      videoShare: row.share_video_pct ?? 0,
      hasError: row.status !== 'success',
      concentrated: row.concentrated_over_90pct,
    };
  }) || [];

  return (
    <div className="space-y-6">
      {/* Control Banner & Meta Summary */}
      <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="w-6 h-6 rounded-full bg-sky-500/15 border border-sky-500/40 text-sky-400 font-mono text-xs flex items-center justify-center font-bold">
                <BarChart3 className="w-3.5 h-3.5" />
              </span>
              <h2 className="text-sm font-semibold text-canvas-textPrimary font-mono uppercase tracking-wider">
                Cross-Strategy Benchmark & Mathematical Comparison
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-canvas-textSecondary max-w-3xl leading-relaxed">
              Execute all 8 allocation models simultaneously against your current cover carriers and secret payload.
              Compare exact byte partitions, carrier concentration risks, and theoretical modeled risk proxies without bias.
            </p>
          </div>

          <button
            type="button"
            disabled={!hasCarriers || loading}
            onClick={onRunComparison}
            className={`px-4 py-2 rounded font-mono text-xs font-semibold flex items-center justify-center space-x-2 transition-all shadow-sm ${
              hasCarriers && !loading
                ? 'bg-sky-600 hover:bg-sky-500 text-white cursor-pointer active:scale-95'
                : 'bg-zinc-800 text-zinc-500 border border-zinc-700/50 cursor-not-allowed'
            }`}
          >
            {loading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Solving 8 Allocations...</span>
              </>
            ) : (
              <>
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Compare All 8 Strategies</span>
              </>
            )}
          </button>
        </div>

        {/* Input Readiness Indicators */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-3 border-t border-canvas-borderSubtle text-xs font-mono">
          <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated/60 p-2.5 space-y-1">
            <span className="text-zinc-500 text-[10px] uppercase tracking-wider block">Carriers Status</span>
            <div className="flex items-center space-x-1.5">
              {hasCarriers ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-zinc-200 font-semibold truncate">3/3 Carriers Ready</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                  <span className="text-amber-300 font-semibold">Missing Triad Files</span>
                </>
              )}
            </div>
          </div>

          <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated/60 p-2.5 space-y-1">
            <span className="text-zinc-500 text-[10px] uppercase tracking-wider block">Target Payload</span>
            <div className="text-zinc-200 font-semibold">
              {compareData ? `${compareData.payload_bytes.toLocaleString()} B` : (message ? `${(new TextEncoder().encode(message).length + 28).toLocaleString()} B` : 'Default (~15%)')}
            </div>
          </div>

          <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated/60 p-2.5 space-y-1">
            <span className="text-zinc-500 text-[10px] uppercase tracking-wider block">Total Net Capacity</span>
            <div className="text-zinc-200 font-semibold">
              {compareData ? `${compareData.total_net_capacity_bytes.toLocaleString()} B` : 'Requires Profiling'}
            </div>
          </div>

          <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated/60 p-2.5 space-y-1">
            <span className="text-zinc-500 text-[10px] uppercase tracking-wider block">Complexity Scores (I/A/V)</span>
            <div className="text-zinc-200 font-semibold">
              {compareData ? `${compareData.image_complexity_score} / ${compareData.audio_complexity_score} / ${compareData.video_complexity_score}` : 'Pending'}
            </div>
          </div>
        </div>

        {error && (
          <div className="rounded border border-red-500/40 bg-red-950/20 p-3 text-xs font-mono text-red-300 flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Comparison Visualizations & Table */}
      {compareData && (
        <div className="space-y-6">
          {/* Chart Header & Toggle */}
          <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="space-y-0.5">
                <h3 className="text-xs font-mono font-semibold text-zinc-200 flex items-center space-x-2">
                  <BarChart3 className="w-4 h-4 text-sky-400" />
                  <span>Comparative Allocation Profile</span>
                </h3>
                <p className="text-[11px] font-mono text-zinc-500">
                  Visual distribution across all 8 allocation paradigms (including 3 portfolio risk postures)
                </p>
              </div>

              <div className="inline-flex rounded border border-canvas-borderSubtle bg-canvas-elevated p-0.5 font-mono text-[11px]">
                <button
                  type="button"
                  onClick={() => setChartView('shares')}
                  className={`px-2.5 py-1 rounded transition-colors ${
                    chartView === 'shares'
                      ? 'bg-zinc-800 text-sky-300 font-semibold border border-zinc-700/60'
                      : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  Carrier Shares (%)
                </button>
                <button
                  type="button"
                  onClick={() => setChartView('risk')}
                  className={`px-2.5 py-1 rounded transition-colors ${
                    chartView === 'risk'
                      ? 'bg-zinc-800 text-sky-300 font-semibold border border-zinc-700/60'
                      : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  Modeled Risk Proxy (bᵀΣb)
                </button>
              </div>
            </div>

            {/* Recharts Bar Chart */}
            <div className="h-64 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                {chartView === 'shares' ? (
                  <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 25 }}>
                    <XAxis 
                      dataKey="name" 
                      tick={{ fill: '#a1a1aa', fontSize: 10, fontFamily: 'monospace' }} 
                      interval={0}
                      angle={-25}
                      textAnchor="end"
                    />
                    <YAxis 
                      domain={[0, 100]} 
                      tick={{ fill: '#71717a', fontSize: 10, fontFamily: 'monospace' }} 
                      unit="%" 
                    />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: '#18181b', 
                        borderColor: '#27272a', 
                        borderRadius: '0.375rem',
                        fontSize: '11px',
                        fontFamily: 'monospace'
                      }}
                      formatter={(val: any, name: string) => [`${val}%`, name]}
                    />
                    <Legend 
                      wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace', paddingTop: '10px' }} 
                    />
                    <Bar dataKey="imageShare" name="Image Share %" stackId="a" fill="#38bdf8" />
                    <Bar dataKey="audioShare" name="Audio Share %" stackId="a" fill="#34d399" />
                    <Bar dataKey="videoShare" name="Video Share %" stackId="a" fill="#c084fc" />
                  </BarChart>
                ) : (
                  <BarChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 25 }}>
                    <XAxis 
                      dataKey="name" 
                      tick={{ fill: '#a1a1aa', fontSize: 10, fontFamily: 'monospace' }} 
                      interval={0}
                      angle={-25}
                      textAnchor="end"
                    />
                    <YAxis 
                      tick={{ fill: '#71717a', fontSize: 10, fontFamily: 'monospace' }} 
                    />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: '#18181b', 
                        borderColor: '#27272a', 
                        borderRadius: '0.375rem',
                        fontSize: '11px',
                        fontFamily: 'monospace'
                      }}
                      formatter={(val: any) => [Number(val).toLocaleString(), 'Modeled Risk Proxy (bᵀΣb)']}
                    />
                    <Bar dataKey="riskProxy" name="Modeled Risk Proxy (bᵀΣb)">
                      {chartData.map((entry, index) => (
                        <Cell 
                          key={`cell-${index}`} 
                          fill={entry.isNovel ? '#38bdf8' : (entry.concentrated ? '#f59e0b' : '#64748b')} 
                        />
                      ))}
                    </Bar>
                  </BarChart>
                )}
              </ResponsiveContainer>
            </div>

            <div className="rounded border border-canvas-borderSubtle bg-zinc-900/50 p-2.5 text-[11px] font-mono text-zinc-400 flex items-start space-x-2">
              <Info className="w-3.5 h-3.5 text-sky-400 mt-0.5 flex-shrink-0" />
              <span>
                <strong>Methodology Disclosure:</strong> Modeled Risk Proxy (bᵀΣb) represents the mathematical quadratic objective minimized by the Markowitz SLSQP solver using the regularized diagonal covariance matrix Σ. It is the optimizer's internal proxy, not an empirical steganalytic detectability score.
              </span>
            </div>
          </div>

          {/* Detailed Results Table */}
          <div className="rounded-lg border border-canvas-border bg-canvas-surface overflow-hidden shadow-sm">
            <div className="p-4 border-b border-canvas-borderSubtle bg-canvas-elevated/40 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-xs font-mono font-semibold text-zinc-200">
                  Live Strategy Allocation Matrix
                </h3>
                <p className="text-[11px] font-mono text-zinc-500">
                  Live results computed directly from strategy allocate() methods with zero pre-computed values.
                </p>
              </div>
              <span className="text-[10px] font-mono text-zinc-400 bg-zinc-800/80 px-2 py-0.5 rounded border border-zinc-700/60 self-start sm:self-auto">
                {compareData.rows.length} Experimental Configurations
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs">
                <thead className="bg-zinc-900/90 text-[11px] text-zinc-400 border-b border-canvas-borderSubtle">
                  <tr>
                    <th className="py-2.5 px-3 font-semibold">Strategy</th>
                    <th className="py-2.5 px-2.5 font-semibold text-right">Img (B)</th>
                    <th className="py-2.5 px-2.5 font-semibold text-right">Aud (B)</th>
                    <th className="py-2.5 px-2.5 font-semibold text-right">Vid (B)</th>
                    <th className="py-2.5 px-3 font-semibold text-center">Shares (I / A / V %)</th>
                    <th className="py-2.5 px-2.5 font-semibold text-right">Img PSNR</th>
                    <th className="py-2.5 px-2.5 font-semibold text-right">Aud SNR</th>
                    <th className="py-2.5 px-2.5 font-semibold text-right">Vid PSNR</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Modeled Risk (bᵀΣb)</th>
                    <th className="py-2.5 px-3 font-semibold text-center">Concentration Flag</th>
                    {onSelectStrategy && <th className="py-2.5 px-2 font-semibold text-center">Action</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-canvas-borderSubtle">
                  {compareData.rows.map((row, idx) => {
                    const isPort = row.is_novel;
                    const isError = row.status !== 'success';

                    return (
                      <tr
                        key={idx}
                        className={`transition-colors ${
                          isPort 
                            ? 'bg-sky-950/20 hover:bg-sky-950/30' 
                            : 'hover:bg-canvas-elevated/40'
                        }`}
                      >
                        {/* Strategy Name & Badges */}
                        <td className="py-3 px-3">
                          <div className="flex items-center space-x-2">
                            {isPort && (
                              <div className="w-1 h-5 bg-sky-400 rounded-full flex-shrink-0" />
                            )}
                            <div>
                              <div className="font-semibold text-zinc-200 flex items-center space-x-1.5">
                                <span>{row.strategy_name}</span>
                                {isPort && (
                                  <span className="text-[9px] bg-sky-900/80 text-sky-200 px-1 py-0.2 rounded border border-sky-600/60 uppercase font-bold tracking-wide">
                                    NOVEL
                                  </span>
                                )}
                              </div>
                              {row.lambda_param !== null && row.lambda_param !== undefined && (
                                <div className="text-[10px] text-zinc-500">
                                  Risk Tolerance λ = {row.lambda_param.toFixed(2)}
                                </div>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* Img (B) */}
                        <td className="py-3 px-2.5 text-right font-semibold text-zinc-300">
                          {isError || row.b_image == null ? 'N/A' : row.b_image.toLocaleString()}
                        </td>

                        {/* Aud (B) */}
                        <td className="py-3 px-2.5 text-right font-semibold text-zinc-300">
                          {isError || row.b_audio == null ? 'N/A' : row.b_audio.toLocaleString()}
                        </td>

                        {/* Vid (B) */}
                        <td className="py-3 px-2.5 text-right font-semibold text-zinc-300">
                          {isError || row.b_video == null ? 'N/A' : row.b_video.toLocaleString()}
                        </td>

                        {/* Shares (I / A / V %) */}
                        <td className="py-3 px-3 text-center">
                          {isError || row.share_image_pct == null ? (
                            <span className="text-zinc-600">N/A</span>
                          ) : (
                            <div className="flex items-center justify-center space-x-1 text-[11px]">
                              <span className="text-sky-400 font-semibold">{row.share_image_pct}%</span>
                              <span className="text-zinc-600">/</span>
                              <span className="text-emerald-400 font-semibold">{row.share_audio_pct}%</span>
                              <span className="text-zinc-600">/</span>
                              <span className="text-purple-400 font-semibold">{row.share_video_pct}%</span>
                            </div>
                          )}
                        </td>

                        {/* Img PSNR */}
                        <td className="py-3 px-2.5 text-right text-zinc-300">
                          {isError ? 'N/A' : (row.image_psnr_db != null ? `${row.image_psnr_db.toFixed(1)} dB` : '—')}
                        </td>

                        {/* Aud SNR */}
                        <td className="py-3 px-2.5 text-right text-zinc-300">
                          {isError ? 'N/A' : (row.audio_snr_db != null ? `${row.audio_snr_db.toFixed(1)} dB` : '—')}
                        </td>

                        {/* Vid PSNR */}
                        <td className="py-3 px-2.5 text-right text-zinc-300">
                          {isError ? 'N/A' : (row.video_psnr_db != null ? `${row.video_psnr_db.toFixed(1)} dB` : '—')}
                        </td>

                        {/* Modeled Risk Proxy */}
                        <td className="py-3 px-3 text-right">
                          {isError || row.modeled_risk_proxy == null ? (
                            <span className="text-zinc-600">N/A</span>
                          ) : (
                            <span className={`font-semibold ${isPort ? 'text-sky-300 font-bold' : 'text-zinc-300'}`}>
                              {row.modeled_risk_proxy.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                            </span>
                          )}
                        </td>

                        {/* Concentration Flag */}
                        <td className="py-3 px-3 text-center">
                          {isError ? (
                            <span className="text-red-400 text-[10px]">Failed</span>
                          ) : row.concentrated_over_90pct ? (
                            <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950/80 text-amber-300 border border-amber-600/70">
                              <AlertTriangle className="w-3 h-3 text-amber-400" />
                              <span>&gt;90% {row.concentrated_carrier?.toUpperCase()}</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-950/50 text-emerald-300 border border-emerald-800/50">
                              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                              <span>Balanced</span>
                            </span>
                          )}
                        </td>

                        {/* Optional Adopt Strategy button */}
                        {onSelectStrategy && (
                          <td className="py-3 px-2 text-center">
                            <button
                              type="button"
                              onClick={() => onSelectStrategy(row.strategy_key, row.lambda_param ?? undefined)}
                              className="px-2 py-1 rounded text-[10px] font-mono text-zinc-400 hover:text-sky-300 hover:bg-sky-950/40 border border-transparent hover:border-sky-800/50 transition-colors"
                              title="Select this strategy for embedding"
                            >
                              <ArrowRight className="w-3 h-3 inline" />
                            </button>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
