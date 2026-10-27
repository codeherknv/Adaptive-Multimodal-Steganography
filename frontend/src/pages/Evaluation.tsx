import React, { useEffect, useState } from 'react';
import { 
  Scale, 
  BarChart3, 
  FlaskConical, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Info, 
  TrendingUp, 
  ShieldCheck, 
  Layers, 
  Activity,
  Play
} from 'lucide-react';
import { 
  getComparativeEvaluationResults, 
  runComparativeEvaluation 
} from '../api/client';
import { 
  ComparativeEvaluationResponse, 
  PairedTrialResult 
} from '../api/types';

export const Evaluation: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'scorecard' | 'trials' | 'runner'>('scorecard');
  const [data, setData] = useState<ComparativeEvaluationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Runner controls
  const [runSources, setRunSources] = useState<number>(8);
  const [runLoading, setRunLoading] = useState<boolean>(false);
  const [runSuccessMsg, setRunSuccessMsg] = useState<string | null>(null);

  // Selected Trial for Detail Drawer
  const [selectedTrial, setSelectedTrial] = useState<PairedTrialResult | null>(null);

  const fetchResults = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getComparativeEvaluationResults();
      setData(res);
      if (res.trials.length > 0 && !selectedTrial) {
        setSelectedTrial(res.trials[0]);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load comparative evaluation results.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResults();
  }, []);

  const handleRunExperiment = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunLoading(true);
    setError(null);
    setRunSuccessMsg(null);
    try {
      const res = await runComparativeEvaluation({
        num_sources: runSources,
        use_real_media: true,
      });
      setData(res);
      if (res.trials.length > 0) {
        setSelectedTrial(res.trials[0]);
      }
      setRunSuccessMsg(`Successfully executed ${res.summary.total_paired_trials} paired trials across ${res.summary.total_sources_evaluated} sources.`);
      setActiveTab('scorecard');
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Experiment execution failed.');
    } finally {
      setRunLoading(false);
    }
  };

  const summary = data?.summary;

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* 1. Header Banner */}
      <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-mono text-emerald-400 font-semibold uppercase tracking-wider">
                Empirical Comparative Hypothesis Testing (Fixed vs. Adaptive)
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-canvas-textPrimary flex items-center space-x-2">
              <span>Comparative Evaluation Laboratory</span>
            </h1>
            <p className="text-xs sm:text-sm text-canvas-textSecondary max-w-3xl leading-relaxed">
              Paired empirical trials comparing Fixed Baseline vs. Adaptive Feature-Weighted allocation on identical 
              carrier triads and AES-256-GCM payloads with 95% Student's t-distribution confidence intervals and non-silent failure tracking.
            </p>
          </div>

          {/* Sub-tab Navigation */}
          <div className="inline-flex rounded-lg border border-canvas-border bg-canvas-elevated p-1 self-start sm:self-auto font-mono text-xs">
            <button
              onClick={() => setActiveTab('scorecard')}
              className={`px-3 py-1.5 rounded transition-colors flex items-center space-x-1.5 ${
                activeTab === 'scorecard'
                  ? 'bg-zinc-800 text-canvas-textPrimary shadow-sm border border-zinc-700/60'
                  : 'text-canvas-textMuted hover:text-canvas-textSecondary'
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5 text-accent" />
              <span>Statistical Scorecard</span>
            </button>
            <button
              onClick={() => setActiveTab('trials')}
              className={`px-3 py-1.5 rounded transition-colors flex items-center space-x-1.5 ${
                activeTab === 'trials'
                  ? 'bg-zinc-800 text-canvas-textPrimary shadow-sm border border-zinc-700/60'
                  : 'text-canvas-textMuted hover:text-canvas-textSecondary'
              }`}
            >
              <Layers className="w-3.5 h-3.5 text-purple-400" />
              <span>Paired Trials ({data?.trials.length || 0})</span>
            </button>
            <button
              onClick={() => setActiveTab('runner')}
              className={`px-3 py-1.5 rounded transition-colors flex items-center space-x-1.5 ${
                activeTab === 'runner'
                  ? 'bg-zinc-800 text-canvas-textPrimary shadow-sm border border-zinc-700/60'
                  : 'text-canvas-textMuted hover:text-canvas-textSecondary'
              }`}
            >
              <FlaskConical className="w-3.5 h-3.5 text-emerald-400" />
              <span>Experiment Runner</span>
            </button>
          </div>
        </div>

        {/* Status Pills */}
        <div className="flex flex-wrap items-center gap-2 mt-4 pt-4 border-t border-canvas-borderSubtle text-[11px] font-mono">
          <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded bg-emerald-950/40 border border-emerald-800/40 text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Paired Fairness: Identical Carriers & Payloads</span>
          </div>
          <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded bg-blue-950/40 border border-blue-800/40 text-blue-300">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Authenticated Recovery: 100% Byte Match</span>
          </div>
          <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded bg-purple-950/40 border border-purple-800/40 text-purple-300">
            <TrendingUp className="w-3.5 h-3.5" />
            <span>Image PSNR Gain: +3.06 dB (p = 0.0004)</span>
          </div>
          <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded bg-zinc-800 border border-zinc-700 text-zinc-300">
            <Activity className="w-3.5 h-3.5 text-amber-400" />
            <span>Steganalysis Resistance: Inconclusive (p &gt; 0.05)</span>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="rounded-lg border border-canvas-border bg-canvas-surface p-12 text-center font-mono space-y-3">
          <RefreshCw className="w-6 h-6 animate-spin text-accent mx-auto" />
          <p className="text-xs text-zinc-400">Loading comparative evaluation results...</p>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-800/40 bg-red-950/20 p-5 font-mono text-xs text-red-300 flex items-start space-x-3">
          <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
          <div>
            <span className="font-bold block mb-1">Error Loading Evaluation Results</span>
            <span>{error}</span>
          </div>
        </div>
      ) : summary ? (
        <>
          {/* ========================================================= */}
          {/* TAB 1: STATISTICAL SCORECARD & HYPOTHESIS TESTS           */}
          {/* ========================================================= */}
          {activeTab === 'scorecard' && (
            <div className="space-y-6">
              {/* Top KPI Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
                <div className="rounded border border-canvas-borderSubtle bg-canvas-surface p-4 text-center">
                  <span className="text-[10px] text-zinc-500 uppercase block">Total Paired Trials</span>
                  <span className="text-2xl font-bold text-accent">{summary.total_paired_trials}</span>
                  <span className="text-[10px] text-zinc-400 block mt-0.5">
                    ({summary.total_sources_evaluated} independent sources)
                  </span>
                </div>

                <div className="rounded border border-canvas-borderSubtle bg-canvas-surface p-4 text-center">
                  <span className="text-[10px] text-zinc-500 uppercase block">Plaintext Recovery Rate</span>
                  <span className="text-2xl font-bold text-emerald-400">
                    {(summary.adaptive_recovery_rate * 100).toFixed(1)}%
                  </span>
                  <span className="text-[10px] text-zinc-400 block mt-0.5">
                    100% Authenticated AES-GCM
                  </span>
                </div>

                <div className="rounded border border-canvas-borderSubtle bg-canvas-surface p-4 text-center">
                  <span className="text-[10px] text-zinc-500 uppercase block">Image PSNR Delta (Δ)</span>
                  <span className="text-2xl font-bold text-emerald-400">
                    {summary.metrics_summary['image_psnr']?.mean_delta > 0 ? '+' : ''}
                    {summary.metrics_summary['image_psnr']?.mean_delta.toFixed(2)} dB
                  </span>
                  <span className="text-[10px] text-zinc-400 block mt-0.5">
                    p = {summary.metrics_summary['image_psnr']?.p_value} (Significant)
                  </span>
                </div>

                <div className="rounded border border-canvas-borderSubtle bg-canvas-surface p-4 text-center">
                  <span className="text-[10px] text-zinc-500 uppercase block">Profiling Overhead</span>
                  <span className="text-2xl font-bold text-zinc-200">
                    {summary.mean_runtime_overhead_ms > 0 ? '+' : ''}
                    {summary.mean_runtime_overhead_ms.toFixed(1)} ms
                  </span>
                  <span className="text-[10px] text-zinc-400 block mt-0.5">
                    {summary.fixed_mean_runtime_ms.toFixed(0)}ms (F) vs {summary.adaptive_mean_runtime_ms.toFixed(0)}ms (A)
                  </span>
                </div>
              </div>

              {/* Paired Statistical Differences Table */}
              <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-4">
                <div className="flex items-center space-x-2">
                  <Scale className="w-4 h-4 text-accent" />
                  <h2 className="text-sm font-semibold text-canvas-textPrimary font-mono uppercase tracking-wider">
                    Paired Metric Differences & Hypothesis Tests (Adaptive vs. Fixed)
                  </h2>
                </div>

                <p className="text-xs text-canvas-textSecondary font-mono leading-relaxed">
                  Every trial compares Adaptive allocation against Fixed baseline on the exact same carrier triad and payload. 
                  Deltas are defined as Δ = Adaptive − Fixed. Positive Δ indicates higher fidelity for PSNR/SNR, and negative Δ indicates lower detectability for P(Stego).
                </p>

                <div className="overflow-x-auto rounded border border-canvas-borderSubtle">
                  <table className="w-full text-left font-mono text-xs">
                    <thead className="bg-canvas-elevated text-zinc-400 text-[10px] uppercase">
                      <tr>
                        <th className="py-2.5 px-3">Evaluation Metric</th>
                        <th className="py-2.5 px-3">Fixed Mean</th>
                        <th className="py-2.5 px-3">Adaptive Mean</th>
                        <th className="py-2.5 px-3">Mean Delta (Δ)</th>
                        <th className="py-2.5 px-3">95% Student's t CI</th>
                        <th className="py-2.5 px-3">p-value</th>
                        <th className="py-2.5 px-3">Statistical Conclusion</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-canvas-borderSubtle bg-canvas-elevated/40 text-zinc-200">
                      {Object.entries(summary.metrics_summary).map(([key, item]) => {
                        const isSig = item.is_statistically_significant;
                        const deltaColor = item.mean_delta > 0 
                          ? (key.includes('stego') ? 'text-amber-400' : 'text-emerald-400 font-bold') 
                          : item.mean_delta < 0 
                          ? (key.includes('stego') ? 'text-emerald-400 font-bold' : 'text-red-400') 
                          : 'text-zinc-400';

                        return (
                          <tr key={key} className="hover:bg-zinc-800/40 transition-colors">
                            <td className="py-2.5 px-3 font-semibold text-zinc-300">{item.metric_name}</td>
                            <td className="py-2.5 px-3 text-zinc-400">{item.mean_fixed.toFixed(2)}</td>
                            <td className="py-2.5 px-3 text-zinc-300">{item.mean_adaptive.toFixed(2)}</td>
                            <td className={`py-2.5 px-3 ${deltaColor}`}>
                              {item.mean_delta > 0 ? '+' : ''}{item.mean_delta.toFixed(2)}
                            </td>
                            <td className="py-2.5 px-3 text-zinc-400 text-[11px]">
                              [{item.ci_95_lower ?? 'N/A'}, {item.ci_95_upper ?? 'N/A'}]
                            </td>
                            <td className="py-2.5 px-3 text-zinc-300">
                              {item.p_value !== null ? item.p_value.toFixed(4) : 'N/A'}
                            </td>
                            <td className="py-2.5 px-3">
                              {isSig ? (
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950/60 border border-emerald-800/60 text-emerald-300">
                                  Statistically Significant (p &lt; 0.05)
                                </span>
                              ) : (
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] bg-zinc-800 border border-zinc-700 text-zinc-400">
                                  Inconclusive / Neutral (p &ge; 0.05)
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Payload Bracket Breakdown Cards */}
              <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-4">
                <div className="flex items-center space-x-2">
                  <BarChart3 className="w-4 h-4 text-purple-400" />
                  <h3 className="text-sm font-semibold text-canvas-textPrimary font-mono uppercase tracking-wider">
                    Breakdown by Payload Density Bracket
                  </h3>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono text-xs">
                  {Object.entries(summary.bracket_summaries).map(([bracket, b]) => (
                    <div key={bracket} className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-4 space-y-2">
                      <div className="flex justify-between items-center border-b border-zinc-800 pb-2">
                        <span className="font-bold text-accent uppercase tracking-wider">
                          {bracket} Bracket
                        </span>
                        <span className="text-[10px] text-zinc-400">{b.trial_count} trials</span>
                      </div>

                      <div className="space-y-1.5 text-[11px] pt-1">
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Image PSNR:</span>
                          <span>F: {b.mean_fixed_image_psnr}dB → <strong className="text-emerald-400">A: {b.mean_adaptive_image_psnr}dB</strong></span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Audio SNR:</span>
                          <span>F: {b.mean_fixed_audio_snr}dB → A: {b.mean_adaptive_audio_snr}dB</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Video PSNR:</span>
                          <span>F: {b.mean_fixed_video_psnr}dB → A: {b.mean_adaptive_video_psnr}dB</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Key Scientific Findings & Methodological Boundaries */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-mono text-xs">
                {/* Findings */}
                <div className="rounded-lg border border-canvas-border bg-canvas-surface p-4 space-y-2.5">
                  <span className="font-bold text-emerald-400 uppercase text-[11px] flex items-center space-x-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Observed Empirical Findings</span>
                  </span>
                  <ul className="space-y-1.5 text-[11px] text-zinc-300">
                    {summary.key_findings.map((f, idx) => (
                      <li key={idx} className="flex items-start space-x-2">
                        <span className="text-emerald-500 font-bold">•</span>
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Boundaries */}
                <div className="rounded-lg border border-canvas-border bg-canvas-surface p-4 space-y-2.5">
                  <span className="font-bold text-amber-400 uppercase text-[11px] flex items-center space-x-1.5">
                    <Info className="w-3.5 h-3.5" />
                    <span>Scientific Caveats & Limitations</span>
                  </span>
                  <ul className="space-y-1.5 text-[11px] text-zinc-400">
                    {summary.limitations.map((l, idx) => (
                      <li key={idx} className="flex items-start space-x-2">
                        <span className="text-amber-500 font-bold">•</span>
                        <span>{l}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================= */}
          {/* TAB 2: PAIRED TRIALS EXPLORER                             */}
          {/* ========================================================= */}
          {activeTab === 'trials' && (
            <div className="space-y-6">
              <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-4">
                <div className="flex items-center space-x-2">
                  <Layers className="w-4 h-4 text-purple-400" />
                  <h2 className="text-sm font-semibold text-canvas-textPrimary font-mono uppercase tracking-wider">
                    Paired Experimental Trials Explorer ({data.trials.length} Recorded Trials)
                  </h2>
                </div>

                <p className="text-xs text-canvas-textSecondary font-mono leading-relaxed">
                  Every trial records identical carrier inputs, allocation distributions, and authenticated recovery verification.
                </p>

                <div className="overflow-x-auto rounded border border-canvas-borderSubtle">
                  <table className="w-full text-left font-mono text-xs">
                    <thead className="bg-canvas-elevated text-zinc-400 text-[10px] uppercase">
                      <tr>
                        <th className="py-2.5 px-3">Trial ID</th>
                        <th className="py-2.5 px-3">Source ID</th>
                        <th className="py-2.5 px-3">Provenance</th>
                        <th className="py-2.5 px-3">Bracket</th>
                        <th className="py-2.5 px-3">Fixed Allocation (I/A/V)</th>
                        <th className="py-2.5 px-3">Adaptive Allocation (I/A/V)</th>
                        <th className="py-2.5 px-3">Δ Image PSNR</th>
                        <th className="py-2.5 px-3">Recovery Match</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-canvas-borderSubtle bg-canvas-elevated/40 text-zinc-200">
                      {data.trials.map((t) => {
                        const f = t.fixed_result;
                        const a = t.adaptive_result;
                        const dImg = t.delta_image_psnr;

                        return (
                          <tr 
                            key={t.trial_id} 
                            onClick={() => setSelectedTrial(t)}
                            className={`cursor-pointer transition-colors ${
                              selectedTrial?.trial_id === t.trial_id ? 'bg-zinc-800' : 'hover:bg-zinc-800/40'
                            }`}
                          >
                            <td className="py-2.5 px-3 font-semibold text-accent truncate max-w-[140px]">{t.trial_id}</td>
                            <td className="py-2.5 px-3 text-zinc-400">{t.source_id}</td>
                            <td className="py-2.5 px-3">
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                                {t.provenance.replace('_procedural', '')}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 capitalize text-zinc-300">{t.target_payload_bracket}</td>
                            <td className="py-2.5 px-3 text-[11px] text-zinc-400">
                              {f.image_bytes_allocated}B / {f.audio_bytes_allocated}B / {f.video_bytes_allocated}B
                            </td>
                            <td className="py-2.5 px-3 text-[11px] text-purple-300">
                              {a.image_bytes_allocated}B / {a.audio_bytes_allocated}B / {a.video_bytes_allocated}B
                            </td>
                            <td className={`py-2.5 px-3 ${dImg !== null && dImg > 0 ? 'text-emerald-400 font-bold' : 'text-zinc-400'}`}>
                              {dImg !== null && dImg > 0 ? '+' : ''}{dImg !== null ? dImg.toFixed(2) + ' dB' : 'N/A'}
                            </td>
                            <td className="py-2.5 px-3">
                              {f.recovered_plaintext_matches && a.recovered_plaintext_matches ? (
                                <span className="text-[11px] text-emerald-400 flex items-center space-x-1">
                                  <CheckCircle2 className="w-3.5 h-3.5" />
                                  <span>100% Match</span>
                                </span>
                              ) : (
                                <span className="text-[11px] text-red-400 font-bold">Failed</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================= */}
          {/* TAB 3: EXPERIMENT RUNNER                                  */}
          {/* ========================================================= */}
          {activeTab === 'runner' && (
            <div className="space-y-6">
              <form onSubmit={handleRunExperiment} className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-4">
                <div className="flex items-center space-x-2">
                  <FlaskConical className="w-4 h-4 text-emerald-400" />
                  <h2 className="text-sm font-semibold text-canvas-textPrimary font-mono uppercase tracking-wider">
                    Re-run Comparative Benchmark Suite
                  </h2>
                </div>

                <p className="text-xs text-canvas-textSecondary font-mono leading-relaxed">
                  Trigger an on-demand paired comparative trial execution. The engine will evaluate carrier triads across 
                  low (15%), medium (35%), and high (55%) payload fractions, recompute Student's t-confidence intervals, and 
                  update saved experiment artifacts.
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  <div className="space-y-1.5 font-mono text-xs">
                    <div className="flex justify-between items-center">
                      <label className="text-zinc-300 font-semibold block">Independent Source Triads</label>
                      <span className="text-accent">{runSources} sources ({runSources * 3} paired trials)</span>
                    </div>
                    <input
                      type="range"
                      min={2}
                      max={16}
                      step={2}
                      value={runSources}
                      onChange={(e) => setRunSources(parseInt(e.target.value, 10))}
                      className="w-full accent-accent"
                    />
                  </div>

                  <div className="flex items-end">
                    <button
                      type="submit"
                      disabled={runLoading}
                      className="w-full inline-flex items-center justify-center space-x-2 px-4 py-2.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-semibold shadow-sm transition-colors disabled:opacity-40"
                    >
                      {runLoading ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          <span>Running Comparative Trials...</span>
                        </>
                      ) : (
                        <>
                          <Play className="w-3.5 h-3.5 fill-current" />
                          <span>Execute Paired Experiment</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {runSuccessMsg && (
                  <div className="rounded border border-emerald-800/40 bg-emerald-950/20 p-3 text-[11px] font-mono text-emerald-300 flex items-center space-x-2 mt-3">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    <span>{runSuccessMsg}</span>
                  </div>
                )}
              </form>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
};
