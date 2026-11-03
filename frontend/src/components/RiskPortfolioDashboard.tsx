import React, { useState } from 'react';
import { 
  BarChart3, 
  ShieldAlert, 
  Sliders, 
  TrendingUp, 
  Info, 
  Layers, 
  CheckCircle2, 
  AlertTriangle,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { PortfolioMetadata } from '../api/types';

interface RiskPortfolioDashboardProps {
  portfolioMetadata?: PortfolioMetadata | null;
  totalPayloadBytes?: number;
  allocations?: Record<string, {
    payload_bytes: number;
    utilization_ratio?: number;
    weight?: number;
    carrier_usable_capacity_bytes?: number;
    carrier_net_capacity_bytes?: number;
    reason?: string;
  }>;
  riskTolerance: number;
  onRiskToleranceChange?: (val: number) => void;
  isSimulated?: boolean;
}

export const RiskPortfolioDashboard: React.FC<RiskPortfolioDashboardProps> = ({
  portfolioMetadata,
  totalPayloadBytes,
  allocations,
  riskTolerance,
  onRiskToleranceChange,
  isSimulated = false,
}) => {
  const [showFrontierTable, setShowFrontierTable] = useState<boolean>(false);
  const [selectedPointIndex, setSelectedPointIndex] = useState<number | null>(null);

  if (!portfolioMetadata) {
    return (
      <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated/40 p-4 font-mono text-xs text-canvas-textMuted flex items-center space-x-2">
        <Info className="w-4 h-4 text-accent flex-shrink-0" />
        <span>Portfolio metadata will be computed once carriers are profiled or payload is allocated.</span>
      </div>
    );
  }

  const {
    relative_risk,
    unnormalized_variance,
    v_min,
    v_max,
    covariance_matrix,
    carrier_names,
    was_regularized,
    original_min_eigenvalue,
    notes,
    efficient_frontier = [],
    comparison_points = {}
  } = portfolioMetadata;

  // Format relative risk
  const hasRelativeRisk = typeof relative_risk === 'number';
  const riskPercent = hasRelativeRisk ? Math.max(0, Math.min(100, relative_risk * 100)) : null;

  // Prepare frontier chart coordinates
  const maxPayload = efficient_frontier.length > 0 
    ? Math.max(...efficient_frontier.map(p => p.payload_bytes), 1) 
    : 1;
  const maxVariance = efficient_frontier.length > 0 
    ? Math.max(...efficient_frontier.map(p => p.unnormalized_variance), 1) 
    : 1;

  // Chart dimensions for SVG
  const svgWidth = 560;
  const svgHeight = 200;
  const padding = { top: 20, right: 30, bottom: 35, left: 60 };
  const plotWidth = svgWidth - padding.left - padding.right;
  const plotHeight = svgHeight - padding.top - padding.bottom;

  const pointsSvg = efficient_frontier.map(p => {
    const x = padding.left + (p.payload_bytes / maxPayload) * plotWidth;
    const y = padding.top + plotHeight - (p.unnormalized_variance / maxVariance) * plotHeight;
    return { ...p, x, y };
  });

  const pathD = pointsSvg.length > 1
    ? pointsSvg.reduce((acc, pt, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`, '')
    : '';

  // Operating point
  const currentB = totalPayloadBytes ?? 0;
  const currentVar = unnormalized_variance ?? 0;
  const currentX = padding.left + (Math.min(currentB, maxPayload) / maxPayload) * plotWidth;
  const currentY = padding.top + plotHeight - (Math.min(currentVar, maxVariance) / maxVariance) * plotHeight;

  return (
    <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 space-y-6 font-mono text-xs">
      {/* ----------------------------------------------------------------- */}
      {/* 1. Header & Relative Risk KPI                                     */}
      {/* ----------------------------------------------------------------- */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-canvas-borderSubtle">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-accent" />
            <span className="text-sm font-semibold text-canvas-textPrimary uppercase tracking-wider">
              Markowitz Risk-Portfolio Dashboard
            </span>
            {isSimulated && (
              <span className="text-[10px] bg-accent/15 border border-accent/30 text-accent px-1.5 py-0.5 rounded font-bold uppercase">
                Simulated
              </span>
            )}
          </div>
          <p className="text-[11px] text-canvas-textMuted">
            Quadratic payload allocation balancing cross-carrier variance proxy against capacity proportionality.
          </p>
        </div>

        {onRiskToleranceChange && (
          <div className="flex items-center space-x-2 bg-canvas-elevated border border-canvas-borderSubtle px-3 py-1.5 rounded">
            <Sliders className="w-3.5 h-3.5 text-accent" />
            <span className="text-[11px] text-zinc-400">Tolerance &lambda;:</span>
            <span className="text-zinc-200 font-bold">{riskTolerance.toFixed(2)}</span>
          </div>
        )}
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {/* Total Encrypted Payload */}
        <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 space-y-1">
          <span className="text-[10px] text-canvas-textMuted uppercase font-semibold">Total Payload (B)</span>
          <div className="text-base font-bold text-accent">
            {typeof totalPayloadBytes === 'number' ? `${totalPayloadBytes.toLocaleString()} B` : 'N/A'}
          </div>
          <div className="text-[10px] text-zinc-500">Encrypted envelope bytes</div>
        </div>

        {/* Heuristic Relative Risk Score */}
        <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 space-y-1">
          <span className="text-[10px] text-canvas-textMuted uppercase font-semibold">Relative Risk Index</span>
          <div className="text-base font-bold text-zinc-200">
            {hasRelativeRisk ? relative_risk!.toFixed(3) : 'N/A'}
          </div>
          <div className="text-[10px] text-zinc-500">
            {hasRelativeRisk ? `${riskPercent!.toFixed(1)}% of feasible range` : 'Requires payload'}
          </div>
        </div>

        {/* Portfolio Variance (b^T Sigma b) */}
        <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 space-y-1">
          <span className="text-[10px] text-canvas-textMuted uppercase font-semibold">Variance Proxy (b&sup2;&Sigma;)</span>
          <div className="text-base font-bold text-zinc-200">
            {typeof unnormalized_variance === 'number' ? unnormalized_variance.toFixed(1) : 'N/A'}
          </div>
          <div className="text-[10px] text-zinc-500">Quadratic risk penalty</div>
        </div>

        {/* Feasible Variance Bounds */}
        <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 space-y-1">
          <span className="text-[10px] text-canvas-textMuted uppercase font-semibold">Polytope Bounds</span>
          <div className="text-xs font-bold text-zinc-300 pt-0.5">
            {typeof v_min === 'number' && typeof v_max === 'number'
              ? `[${v_min.toFixed(0)}, ${v_max.toFixed(0)}]`
              : 'N/A'}
          </div>
          <div className="text-[10px] text-zinc-500">[V_min, V_max] over S(B)</div>
        </div>
      </div>

      {/* Relative Risk Progress Bar */}
      {hasRelativeRisk && (
        <div className="space-y-1.5 rounded border border-canvas-borderSubtle bg-canvas-elevated/40 p-3">
          <div className="flex justify-between items-center text-[11px]">
            <span className="text-zinc-300 font-semibold flex items-center space-x-1.5">
              <span>Feasible Relative Risk Spectrum:</span>
              <span className="text-accent font-bold">{relative_risk!.toFixed(3)}</span>
            </span>
            <span className="text-zinc-500 text-[10px]">
              0.0 = Min-Variance (Stealth Proxy) &bull; 1.0 = Max-Variance Polytope Vertex
            </span>
          </div>

          <div className="w-full h-2 rounded bg-zinc-900 border border-zinc-800 overflow-hidden relative">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 via-sky-500 to-amber-500 transition-all duration-300"
              style={{ width: `${riskPercent}%` }}
            />
          </div>

          <p className="text-[10px] text-canvas-textMuted leading-relaxed pt-1">
            <strong>Heuristic Methodology Notice:</strong> The Relative Risk Index measures the solution's distance between
            minimal variance V_min and maximal vertex variance V_max over the feasible polytope S(B).
            Minimizing this quadratic proxy does not guarantee undetectability against trained machine-learning steganalysis.
          </p>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* 2. Carrier Allocation Breakdown                                   */}
      {/* ----------------------------------------------------------------- */}
      {allocations && (
        <div className="space-y-3">
          <div className="flex items-center space-x-1.5 text-zinc-300 font-semibold text-xs">
            <Layers className="w-3.5 h-3.5 text-accent" />
            <span>Optimal Carrier Byte Distribution</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {['image', 'audio', 'video'].map((carrier) => {
              const alloc = allocations[carrier];
              if (!alloc) return null;
              const bytes = alloc.payload_bytes;
              const total = totalPayloadBytes && totalPayloadBytes > 0 ? totalPayloadBytes : 1;
              const pct = ((bytes / total) * 100).toFixed(1);
              const util = alloc.utilization_ratio ? (alloc.utilization_ratio * 100).toFixed(1) : '0.0';

              return (
                <div key={carrier} className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="font-semibold uppercase text-zinc-200 text-xs">
                      {carrier} Carrier
                    </span>
                    <span className="text-accent font-bold text-xs">
                      {bytes.toLocaleString()} B ({pct}%)
                    </span>
                  </div>

                  <div className="w-full h-1.5 rounded bg-zinc-900 border border-zinc-800 overflow-hidden">
                    <div
                      className={`h-full ${
                        carrier === 'image' ? 'bg-sky-400' : carrier === 'audio' ? 'bg-emerald-400' : 'bg-purple-400'
                      }`}
                      style={{ width: `${Math.min(100, Math.max(0, Number(pct)))}%` }}
                    />
                  </div>

                  <div className="text-[10px] space-y-1 text-canvas-textMuted border-t border-zinc-800/80 pt-1.5">
                    <div className="flex justify-between">
                      <span>Usable Capacity:</span>
                      <span className="text-zinc-300">
                        {alloc.carrier_usable_capacity_bytes?.toLocaleString() ?? 'N/A'} B
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Carrier Utilization:</span>
                      <span className="text-zinc-300">{util}%</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* 3. Covariance Matrix & Spectral Regularization                    */}
      {/* ----------------------------------------------------------------- */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs gap-2">
          <span className="text-zinc-300 font-semibold flex items-center space-x-1.5">
            <BarChart3 className="w-3.5 h-3.5 text-accent" />
            <span>Cross-Modal Covariance Matrix (&Sigma;)</span>
          </span>
          <span className="text-[10px] text-zinc-500">
            Derived from inverse complexity variance: &sigma;&sup2; = 1 / (Complexity)&sup2;
          </span>
        </div>

        {was_regularized && (
          <div className="rounded border border-amber-800/40 bg-amber-950/20 p-2.5 text-[11px] text-amber-300 flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-semibold">Spectral Regularization Applied:</p>
              <p className="text-[10px] text-amber-200/80">
                {notes || `Eigenvalue flooring enforced positive-definiteness (min eigenvalue floored from ${original_min_eigenvalue} to 1e-6).`}
              </p>
            </div>
          </div>
        )}

        <div className="overflow-x-auto rounded border border-canvas-borderSubtle bg-canvas-elevated">
          <table className="w-full text-center text-xs">
            <thead className="bg-zinc-900/80 text-zinc-400 border-b border-canvas-borderSubtle text-[11px] uppercase">
              <tr>
                <th className="py-2 px-3 text-left">Carrier</th>
                {carrier_names.map((name) => (
                  <th key={name} className="py-2 px-3">{name}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-canvas-borderSubtle text-zinc-300">
              {covariance_matrix.map((row, i) => (
                <tr key={carrier_names[i] || i} className="hover:bg-zinc-800/30">
                  <td className="py-2 px-3 text-left font-semibold uppercase text-zinc-400 text-[11px]">
                    {carrier_names[i] || `Carrier ${i}`}
                  </td>
                  {row.map((val, j) => (
                    <td
                      key={j}
                      className={`py-2 px-3 font-mono ${
                        i === j ? 'text-accent font-bold bg-accent/5' : 'text-zinc-500'
                      }`}
                    >
                      {val.toFixed(4)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* 4. Markowitz Efficient Frontier Plot                              */}
      {/* ----------------------------------------------------------------- */}
      {efficient_frontier.length > 0 && (
        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs gap-2">
            <span className="text-zinc-300 font-semibold flex items-center space-x-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-accent" />
              <span>Markowitz Efficient Frontier Curve</span>
            </span>
            <button
              type="button"
              onClick={() => setShowFrontierTable(!showFrontierTable)}
              className="text-[11px] text-accent hover:text-accent/80 flex items-center space-x-1"
            >
              <span>{showFrontierTable ? 'Hide Table' : 'Show Frontier Table'}</span>
              {showFrontierTable ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
          </div>

          {/* SVG Frontier Chart */}
          <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 overflow-x-auto">
            <svg
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              className="w-full max-w-full h-auto select-none"
              style={{ minWidth: '450px' }}
            >
              {/* Grid Lines */}
              {[0, 0.25, 0.5, 0.75, 1.0].map((ratio) => {
                const y = padding.top + plotHeight * (1 - ratio);
                const x = padding.left + plotWidth * ratio;
                return (
                  <g key={ratio}>
                    {/* Horizontal grid */}
                    <line
                      x1={padding.left}
                      y1={y}
                      x2={svgWidth - padding.right}
                      y2={y}
                      stroke="#26272e"
                      strokeDasharray="2 3"
                    />
                    <text
                      x={padding.left - 8}
                      y={y + 3}
                      fill="#717382"
                      fontSize="9"
                      textAnchor="end"
                      fontFamily="monospace"
                    >
                      {(maxVariance * ratio).toFixed(0)}
                    </text>

                    {/* Vertical grid */}
                    <line
                      x1={x}
                      y1={padding.top}
                      x2={x}
                      y2={svgHeight - padding.bottom}
                      stroke="#26272e"
                      strokeDasharray="2 3"
                    />
                    <text
                      x={x}
                      y={svgHeight - padding.bottom + 16}
                      fill="#717382"
                      fontSize="9"
                      textAnchor="middle"
                      fontFamily="monospace"
                    >
                      {(maxPayload * ratio).toFixed(0)}B
                    </text>
                  </g>
                );
              })}

              {/* Axis Labels */}
              <text
                x={svgWidth / 2}
                y={svgHeight - 4}
                fill="#a0a2b1"
                fontSize="10"
                textAnchor="middle"
                fontFamily="monospace"
              >
                Payload Envelope (Bytes)
              </text>
              <text
                x={12}
                y={svgHeight / 2}
                fill="#a0a2b1"
                fontSize="10"
                textAnchor="middle"
                transform={`rotate(-90 12 ${svgHeight / 2})`}
                fontFamily="monospace"
              >
                Min Variance V*(B)
              </text>

              {/* Frontier Line */}
              {pathD && (
                <path
                  d={pathD}
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              )}

              {/* Discrete Frontier Points */}
              {pointsSvg.map((pt, idx) => (
                <circle
                  key={idx}
                  cx={pt.x}
                  cy={pt.y}
                  r={selectedPointIndex === idx ? 5 : 3}
                  className="cursor-pointer transition-all"
                  fill={selectedPointIndex === idx ? '#38bdf8' : '#0284c7'}
                  stroke="#16171b"
                  strokeWidth="1.5"
                  onMouseEnter={() => setSelectedPointIndex(idx)}
                  onMouseLeave={() => setSelectedPointIndex(null)}
                />
              ))}

              {/* Current Operating Point */}
              {totalPayloadBytes && totalPayloadBytes > 0 && (
                <g>
                  <circle
                    cx={currentX}
                    cy={currentY}
                    r="6"
                    fill="#10b981"
                    stroke="#ffffff"
                    strokeWidth="1.5"
                  />
                  <text
                    x={currentX + 8}
                    y={Math.max(currentY - 6, padding.top + 10)}
                    fill="#10b981"
                    fontSize="9"
                    fontWeight="bold"
                    fontFamily="monospace"
                  >
                    Current (B={currentB}B)
                  </text>
                </g>
              )}
            </svg>

            {/* Selected Point Details */}
            {selectedPointIndex !== null && efficient_frontier[selectedPointIndex] && (
              <div className="mt-2 p-2 rounded bg-zinc-900 border border-zinc-800 text-[11px] text-zinc-300 flex justify-between items-center">
                <span>
                  Frontier Point: <strong>{efficient_frontier[selectedPointIndex].payload_bytes} B</strong> &bull; Minimal Variance:{' '}
                  <strong>{efficient_frontier[selectedPointIndex].unnormalized_variance.toFixed(2)}</strong>
                </span>
                <span className="text-zinc-500">
                  Img: {efficient_frontier[selectedPointIndex].allocations.image}B &bull; Aud:{' '}
                  {efficient_frontier[selectedPointIndex].allocations.audio}B &bull; Vid:{' '}
                  {efficient_frontier[selectedPointIndex].allocations.video}B
                </span>
              </div>
            )}
          </div>

          {/* Frontier Table (Collapsible) */}
          {showFrontierTable && (
            <div className="overflow-x-auto rounded border border-canvas-borderSubtle bg-canvas-elevated">
              <table className="w-full text-left text-xs">
                <thead className="bg-zinc-900/80 text-zinc-400 border-b border-canvas-borderSubtle text-[11px] uppercase">
                  <tr>
                    <th className="py-2 px-3">Payload (B)</th>
                    <th className="py-2 px-3">Minimal Variance</th>
                    <th className="py-2 px-3">Image Allocation</th>
                    <th className="py-2 px-3">Audio Allocation</th>
                    <th className="py-2 px-3">Video Allocation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-canvas-borderSubtle text-zinc-300">
                  {efficient_frontier.map((pt, i) => (
                    <tr key={i} className="hover:bg-zinc-800/30">
                      <td className="py-1.5 px-3 font-bold text-accent">{pt.payload_bytes} B</td>
                      <td className="py-1.5 px-3">{pt.unnormalized_variance.toFixed(2)}</td>
                      <td className="py-1.5 px-3 text-zinc-400">{pt.allocations.image} B</td>
                      <td className="py-1.5 px-3 text-zinc-400">{pt.allocations.audio} B</td>
                      <td className="py-1.5 px-3 text-zinc-400">{pt.allocations.video} B</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* 5. Matched Baseline Comparison Table                              */}
      {/* ----------------------------------------------------------------- */}
      {comparison_points && Object.keys(comparison_points).length > 0 && (
        <div className="space-y-3 pt-2 border-t border-canvas-borderSubtle">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs gap-2">
            <span className="text-zinc-300 font-semibold flex items-center space-x-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Matched Strategy Comparison (Identical Triad & Payload)</span>
            </span>
            <span className="text-[10px] text-zinc-500 bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded">
              Empirical matched inputs: {totalPayloadBytes} B
            </span>
          </div>

          <div className="overflow-x-auto rounded border border-canvas-borderSubtle bg-canvas-elevated">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-900/80 text-zinc-400 border-b border-canvas-borderSubtle text-[11px] uppercase">
                <tr>
                  <th className="py-2 px-3">Allocation Strategy</th>
                  <th className="py-2 px-3">Image (B)</th>
                  <th className="py-2 px-3">Audio (B)</th>
                  <th className="py-2 px-3">Video (B)</th>
                  <th className="py-2 px-3">Variance Proxy</th>
                  <th className="py-2 px-3">Relative Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-canvas-borderSubtle text-zinc-300">
                {/* 1. Portfolio (Current Strategy) */}
                {allocations && (
                  <tr className="bg-accent/10 hover:bg-accent/15 font-semibold">
                    <td className="py-2 px-3 text-accent flex items-center space-x-1.5">
                      <span className="w-2 h-2 rounded-full bg-accent" />
                      <span>Portfolio (&lambda;={riskTolerance.toFixed(2)})</span>
                    </td>
                    <td className="py-2 px-3 text-zinc-200">{allocations.image?.payload_bytes ?? 0} B</td>
                    <td className="py-2 px-3 text-zinc-200">{allocations.audio?.payload_bytes ?? 0} B</td>
                    <td className="py-2 px-3 text-zinc-200">{allocations.video?.payload_bytes ?? 0} B</td>
                    <td className="py-2 px-3 text-accent">{unnormalized_variance?.toFixed(1) ?? 'N/A'}</td>
                    <td className="py-2 px-3 text-accent">{hasRelativeRisk ? relative_risk!.toFixed(3) : 'N/A'}</td>
                  </tr>
                )}

                {/* 2. Fixed Baseline */}
                {comparison_points.fixed && (
                  <tr className="hover:bg-zinc-800/30">
                    <td className="py-2 px-3 text-zinc-300 font-medium">
                      Fixed Baseline (Equal Split)
                    </td>
                    <td className="py-2 px-3 text-zinc-400">{comparison_points.fixed.allocations.image} B</td>
                    <td className="py-2 px-3 text-zinc-400">{comparison_points.fixed.allocations.audio} B</td>
                    <td className="py-2 px-3 text-zinc-400">{comparison_points.fixed.allocations.video} B</td>
                    <td className="py-2 px-3 text-zinc-300">{comparison_points.fixed.unnormalized_variance.toFixed(1)}</td>
                    <td className="py-2 px-3 text-zinc-300">{comparison_points.fixed.relative_risk.toFixed(3)}</td>
                  </tr>
                )}

                {/* 3. Adaptive Feature */}
                {comparison_points.adaptive && (
                  <tr className="hover:bg-zinc-800/30">
                    <td className="py-2 px-3 text-zinc-300 font-medium">
                      Adaptive (Feature & Capacity Weighted)
                    </td>
                    <td className="py-2 px-3 text-zinc-400">{comparison_points.adaptive.allocations.image} B</td>
                    <td className="py-2 px-3 text-zinc-400">{comparison_points.adaptive.allocations.audio} B</td>
                    <td className="py-2 px-3 text-zinc-400">{comparison_points.adaptive.allocations.video} B</td>
                    <td className="py-2 px-3 text-zinc-300">{comparison_points.adaptive.unnormalized_variance.toFixed(1)}</td>
                    <td className="py-2 px-3 text-zinc-300">{comparison_points.adaptive.relative_risk.toFixed(3)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
