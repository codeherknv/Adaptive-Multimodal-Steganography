import React, { useEffect, useState } from 'react';
import { 
  Cpu, 
  BarChart3, 
  Database, 
  AlertCircle, 
  CheckCircle2, 
  RefreshCw, 
  Search, 
  Image as ImageIcon, 
  Music, 
  Video as VideoIcon,
  Info
} from 'lucide-react';
import { 
  generateSteganalysisDataset, 
  getSteganalysisDatasetSummary, 
  trainSteganalyzers, 
  listTrainedSteganalyzers, 
  classifyMediaFile 
} from '../api/client';
import { 
  SteganalysisDatasetSummary, 
  SteganalysisTrainResponse, 
  SteganalysisClassifyResponse 
} from '../api/types';

export const Steganalysis: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'inspect' | 'evaluate' | 'dataset'>('inspect');

  // Live Inspector State
  const [inspectFile, setInspectFile] = useState<File | null>(null);
  const [inspectModelType, setInspectModelType] = useState<'random_forest' | 'logistic_regression'>('random_forest');
  const [inspectLoading, setInspectLoading] = useState<boolean>(false);
  const [inspectError, setInspectError] = useState<string | null>(null);
  const [inspectResult, setInspectResult] = useState<SteganalysisClassifyResponse | null>(null);

  // Train / Evaluate State
  const [trainModality, setTrainModality] = useState<'image' | 'audio' | 'video' | 'all'>('image');
  const [trainModelType, setTrainModelType] = useState<'random_forest' | 'logistic_regression'>('random_forest');
  const [trainSources, setTrainSources] = useState<number>(12);
  const [trainLoading, setTrainLoading] = useState<boolean>(false);
  const [trainError, setTrainError] = useState<string | null>(null);
  const [trainedModels, setTrainedModels] = useState<SteganalysisTrainResponse[]>([]);
  const [selectedEvaluation, setSelectedEvaluation] = useState<SteganalysisTrainResponse | null>(null);

  // Dataset State
  const [datasetSummaries, setDatasetSummaries] = useState<SteganalysisDatasetSummary[]>([]);
  const [datasetLoading, setDatasetLoading] = useState<boolean>(false);
  const [datasetError, setDatasetError] = useState<string | null>(null);

  // -------------------------------------------------------------
  // Initial Data Fetch
  // -------------------------------------------------------------
  const fetchInitialData = async () => {
    try {
      const [summaries, models] = await Promise.all([
        getSteganalysisDatasetSummary(),
        listTrainedSteganalyzers()
      ]);
      setDatasetSummaries(summaries);
      setTrainedModels(models);
      if (models.length > 0 && !selectedEvaluation) {
        setSelectedEvaluation(models[0]);
      }
    } catch {
      // Non-fatal on mount
    }
  };

  useEffect(() => {
    fetchInitialData();
  }, []);

  // -------------------------------------------------------------
  // Handler: Live File Classification
  // -------------------------------------------------------------
  const handleInspectSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inspectFile) {
      setInspectError('Please select a media file (PNG, WAV, or AVI) to inspect.');
      return;
    }

    setInspectLoading(true);
    setInspectError(null);
    setInspectResult(null);

    try {
      const formData = new FormData();
      formData.append('file', inspectFile);
      formData.append('model_type', inspectModelType);

      const res = await classifyMediaFile(formData);
      setInspectResult(res);
    } catch (err: any) {
      setInspectError(err.response?.data?.detail || err.message || 'Classification failed.');
    } finally {
      setInspectLoading(false);
    }
  };

  // -------------------------------------------------------------
  // Handler: Train & Evaluate Models
  // -------------------------------------------------------------
  const handleTrainSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTrainLoading(true);
    setTrainError(null);

    try {
      const responses = await trainSteganalyzers({
        modality: trainModality,
        model_type: trainModelType,
        num_sources: trainSources,
      });

      setTrainedModels((prev) => {
        const merged = [...responses, ...prev.filter(p => !responses.some(r => r.modality === p.modality && r.model_type === p.model_type))];
        return merged;
      });
      if (responses.length > 0) {
        setSelectedEvaluation(responses[0]);
      }
      // Also update dataset summary
      const summaries = await getSteganalysisDatasetSummary();
      setDatasetSummaries(summaries);
    } catch (err: any) {
      setTrainError(err.response?.data?.detail || err.message || 'Model training failed.');
    } finally {
      setTrainLoading(false);
    }
  };

  // -------------------------------------------------------------
  // Handler: Generate Dataset
  // -------------------------------------------------------------
  const handleGenerateDataset = async () => {
    setDatasetLoading(true);
    setDatasetError(null);
    try {
      const summaries = await generateSteganalysisDataset({
        modality: 'all',
        model_type: 'random_forest',
        num_sources: 12,
      });
      setDatasetSummaries(summaries);
    } catch (err: any) {
      setDatasetError(err.response?.data?.detail || err.message || 'Dataset generation failed.');
    } finally {
      setDatasetLoading(false);
    }
  };

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* Header Banner */}
      <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-accent/10 border border-accent/30 text-accent font-semibold uppercase tracking-wider">
                Phase 7 Steganalysis
              </span>
              <span className="text-xs font-mono text-canvas-textMuted">
                Machine-Learning Detectability & Statistical Artifact Evaluation
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-canvas-textPrimary">
              Steganalysis & Detectability Laboratory
            </h1>
            <p className="text-xs sm:text-sm text-canvas-textSecondary max-w-3xl leading-relaxed">
              Supervised baseline classification (Random Forest & Logistic Regression) evaluating 
              first- and second-order statistical artifact detectability across Image, Audio, and Video carriers with 
              zero-leakage source-group partitioning.
            </p>
          </div>

          {/* Sub-tab Navigation */}
          <div className="inline-flex rounded-lg border border-canvas-border bg-canvas-elevated p-1 self-start sm:self-auto font-mono text-xs">
            <button
              onClick={() => setActiveTab('inspect')}
              className={`px-3 py-1.5 rounded transition-colors flex items-center space-x-1.5 ${
                activeTab === 'inspect'
                  ? 'bg-zinc-800 text-canvas-textPrimary shadow-sm border border-zinc-700/60'
                  : 'text-canvas-textMuted hover:text-canvas-textSecondary'
              }`}
            >
              <Search className="w-3.5 h-3.5 text-accent" />
              <span>Live Carrier Inspector</span>
            </button>
            <button
              onClick={() => setActiveTab('evaluate')}
              className={`px-3 py-1.5 rounded transition-colors flex items-center space-x-1.5 ${
                activeTab === 'evaluate'
                  ? 'bg-zinc-800 text-canvas-textPrimary shadow-sm border border-zinc-700/60'
                  : 'text-canvas-textMuted hover:text-canvas-textSecondary'
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5 text-purple-400" />
              <span>Train & Evaluate</span>
            </button>
            <button
              onClick={() => setActiveTab('dataset')}
              className={`px-3 py-1.5 rounded transition-colors flex items-center space-x-1.5 ${
                activeTab === 'dataset'
                  ? 'bg-zinc-800 text-canvas-textPrimary shadow-sm border border-zinc-700/60'
                  : 'text-canvas-textMuted hover:text-canvas-textSecondary'
              }`}
            >
              <Database className="w-3.5 h-3.5 text-emerald-400" />
              <span>Datasets</span>
            </button>
          </div>
        </div>
      </div>

      {/* ========================================================= */}
      {/* TAB 1: LIVE CARRIER INSPECTOR                             */}
      {/* ========================================================= */}
      {activeTab === 'inspect' && (
        <div className="space-y-6">
          <form onSubmit={handleInspectSubmit} className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-4">
            <div className="flex items-center space-x-2">
              <Search className="w-4 h-4 text-accent" />
              <h2 className="text-sm font-semibold text-canvas-textPrimary font-mono uppercase tracking-wider">
                Upload Media Carrier for Statistical Steganalysis
              </h2>
            </div>

            <p className="text-xs text-canvas-textSecondary font-mono leading-relaxed">
              Upload any PNG image, WAV audio, or AVI video file. The detector will extract first- and second-order 
              statistical features (LSB ratios, PoV asymmetry, residual variances) and output an empirical Cover vs. Stego prediction.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              {/* File Upload */}
              <div className="sm:col-span-2 rounded border border-dashed border-canvas-borderSubtle bg-canvas-elevated/40 p-4 space-y-2">
                <input
                  type="file"
                  accept="image/png,audio/wav,video/avi,video/x-msvideo"
                  onChange={(e) => setInspectFile(e.target.files?.[0] || null)}
                  className="block w-full text-xs font-mono text-zinc-400 file:mr-2 file:py-1 file:px-2.5 file:rounded file:border-0 file:text-[11px] file:font-mono file:bg-zinc-800 file:text-zinc-200 hover:file:bg-zinc-700 cursor-pointer"
                />
                {inspectFile && (
                  <p className="text-[11px] font-mono text-accent truncate">
                    Loaded: {inspectFile.name} ({(inspectFile.size / 1024).toFixed(1)} KB)
                  </p>
                )}
              </div>

              {/* Model Selector */}
              <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated/40 p-4 space-y-2 font-mono text-xs">
                <label className="text-zinc-300 font-semibold block">Classifier Model</label>
                <select
                  value={inspectModelType}
                  onChange={(e) => setInspectModelType(e.target.value as any)}
                  className="w-full rounded border border-canvas-border bg-canvas-elevated px-2.5 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-accent"
                >
                  <option value="random_forest">Random Forest (100 Trees)</option>
                  <option value="logistic_regression">Logistic Regression (L2)</option>
                </select>
                <span className="text-[10px] text-zinc-500 block leading-tight">
                  Supervised baseline trained on procedural covers with GroupShuffleSplit.
                </span>
              </div>
            </div>

            {inspectError && (
              <div className="rounded border border-red-800/40 bg-red-950/20 p-3 text-xs font-mono text-red-300 flex items-start space-x-2">
                <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                <span>{inspectError}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={inspectLoading || !inspectFile}
              className="py-2.5 px-4 rounded text-xs font-mono font-semibold bg-accent text-zinc-950 hover:bg-accent/90 disabled:opacity-40 transition-colors flex items-center justify-center space-x-2 shadow-sm"
            >
              <Search className={`w-3.5 h-3.5 ${inspectLoading ? 'animate-spin' : ''}`} />
              <span>{inspectLoading ? 'Extracting Artifacts & Classifying...' : 'Inspect & Classify Carrier'}</span>
            </button>
          </form>

          {/* Results Card */}
          {inspectResult && (
            <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-5 animate-in fade-in duration-200">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-canvas-borderSubtle gap-3">
                <div className="space-y-0.5">
                  <span className="text-[11px] font-mono uppercase text-zinc-500">Classification Outcome</span>
                  <div className="flex items-center space-x-2.5">
                    <span className={`px-2.5 py-0.5 rounded text-xs font-mono font-bold uppercase border ${
                      inspectResult.predicted_class === 'Stego'
                        ? 'bg-amber-950/40 text-amber-400 border-amber-800/60'
                        : 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60'
                    }`}>
                      Predicted {inspectResult.predicted_class}
                    </span>
                    <span className="text-xs font-mono text-zinc-300">
                      Modality: <span className="font-semibold uppercase text-accent">{inspectResult.modality}</span>
                    </span>
                    {inspectResult.is_calibrated ? (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-950/40 text-purple-300 border border-purple-800/50">
                        {inspectResult.calibration_method}
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-zinc-800 text-zinc-400 border border-zinc-700">
                        Uncalibrated Score
                      </span>
                    )}
                  </div>
                </div>

                <div className="text-right font-mono text-xs">
                  <span className="text-zinc-500 block text-[10px] uppercase">Stego Probability</span>
                  <span className="text-lg font-bold text-zinc-100">
                    {(inspectResult.stego_probability * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Confidence Bar */}
              <div className="space-y-1 font-mono text-xs">
                <div className="flex justify-between text-[11px] text-zinc-400">
                  <span>Cover Probability: {((1.0 - inspectResult.stego_probability) * 100).toFixed(1)}%</span>
                  <span>Stego Probability: {(inspectResult.stego_probability * 100).toFixed(1)}%</span>
                </div>
                <div className="h-2 w-full bg-zinc-800 rounded-full overflow-hidden flex">
                  <div
                    style={{ width: `${(1.0 - inspectResult.stego_probability) * 100}%` }}
                    className="bg-emerald-500 h-full transition-all duration-300"
                  />
                  <div
                    style={{ width: `${inspectResult.stego_probability * 100}%` }}
                    className="bg-amber-500 h-full transition-all duration-300"
                  />
                </div>
              </div>

              {/* Extracted Artifact Features Grid */}
              <div className="space-y-2">
                <h3 className="text-xs font-mono font-semibold text-zinc-300 uppercase tracking-wider flex items-center space-x-1.5">
                  <Cpu className="w-3.5 h-3.5 text-accent" />
                  <span>Extracted Statistical Features ({Object.keys(inspectResult.feature_values).length} metrics)</span>
                </h3>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-xs">
                  {Object.entries(inspectResult.feature_values).map(([name, val]) => (
                    <div key={name} className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-2 space-y-0.5">
                      <span className="text-[10px] text-zinc-500 truncate block" title={name}>
                        {name.replace(/^(img_|aud_|vid_)/, '')}
                      </span>
                      <span className="text-zinc-200 font-bold block">{val}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Scientific Disclaimer */}
              <div className="rounded border border-canvas-borderSubtle bg-zinc-900/60 p-3 text-[11px] font-mono text-zinc-400 flex items-start space-x-2">
                <Info className="w-4 h-4 text-accent mt-0.5 flex-shrink-0" />
                <span>{inspectResult.disclaimer}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================= */}
      {/* TAB 2: TRAIN & EVALUATE DETECTORS                         */}
      {/* ========================================================= */}
      {activeTab === 'evaluate' && (
        <div className="space-y-6">
          {/* Training Control Panel */}
          <form onSubmit={handleTrainSubmit} className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-4">
            <div className="flex items-center space-x-2">
              <BarChart3 className="w-4 h-4 text-purple-400" />
              <h2 className="text-sm font-semibold text-canvas-textPrimary font-mono uppercase tracking-wider">
                Train Baseline Steganalysis Detectors (Zero-Leakage Group Split)
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
              {/* Modality */}
              <div className="space-y-1.5">
                <label className="text-zinc-300 font-semibold block">Target Modality</label>
                <select
                  value={trainModality}
                  onChange={(e) => setTrainModality(e.target.value as any)}
                  className="w-full rounded border border-canvas-border bg-canvas-elevated px-2.5 py-1.5 text-zinc-200 focus:outline-none focus:border-accent"
                >
                  <option value="image">PNG Image (10 Features)</option>
                  <option value="audio">WAV Audio (8 Features)</option>
                  <option value="video">Lossless Video (7 Features)</option>
                  <option value="all">All Three Modalities</option>
                </select>
              </div>

              {/* Model Type */}
              <div className="space-y-1.5">
                <label className="text-zinc-300 font-semibold block">Model Architecture</label>
                <select
                  value={trainModelType}
                  onChange={(e) => setTrainModelType(e.target.value as any)}
                  className="w-full rounded border border-canvas-border bg-canvas-elevated px-2.5 py-1.5 text-zinc-200 focus:outline-none focus:border-accent"
                >
                  <option value="random_forest">Random Forest Classifier</option>
                  <option value="logistic_regression">Logistic Regression</option>
                </select>
              </div>

              {/* Number of Sources */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label className="text-zinc-300 font-semibold block">Source Cover Groups</label>
                  <span className="text-accent">{trainSources} sources</span>
                </div>
                <input
                  type="range"
                  min="6"
                  max="30"
                  value={trainSources}
                  onChange={(e) => setTrainSources(parseInt(e.target.value))}
                  className="w-full accent-accent cursor-pointer"
                />
              </div>
            </div>

            {trainError && (
              <div className="rounded border border-red-800/40 bg-red-950/20 p-3 text-xs font-mono text-red-300 flex items-start space-x-2">
                <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                <span>{trainError}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={trainLoading}
              className="py-2.5 px-4 rounded text-xs font-mono font-semibold bg-purple-500 text-zinc-950 hover:bg-purple-400 disabled:opacity-40 transition-colors flex items-center justify-center space-x-2 shadow-sm"
            >
              <Cpu className={`w-3.5 h-3.5 ${trainLoading ? 'animate-spin' : ''}`} />
              <span>{trainLoading ? 'Partitioning Groups, Fitting Scaler & Training Model...' : 'Train & Evaluate Held-Out Data'}</span>
            </button>
          </form>

          {/* Model Selector Pills */}
          {trainedModels.length > 0 && (
            <div className="flex items-center space-x-2 overflow-x-auto pb-1 text-xs font-mono">
              <span className="text-zinc-500 text-[11px] uppercase">Evaluated Models:</span>
              {trainedModels.map((m, idx) => (
                <button
                  key={`${m.modality}-${m.model_type}-${idx}`}
                  onClick={() => setSelectedEvaluation(m)}
                  className={`px-2.5 py-1 rounded border text-[11px] transition-colors ${
                    selectedEvaluation?.modality === m.modality && selectedEvaluation?.model_type === m.model_type
                      ? 'border-purple-400 bg-purple-950/40 text-purple-300 font-semibold'
                      : 'border-canvas-borderSubtle bg-canvas-elevated text-zinc-400 hover:text-zinc-300'
                  }`}
                >
                  <span className="uppercase font-bold">{m.modality}</span> / {m.model_type === 'random_forest' ? 'RF' : 'LogReg'}
                </button>
              ))}
            </div>
          )}

          {/* Held-Out Evaluation Results Card */}
          {selectedEvaluation && (
            <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-canvas-borderSubtle gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-canvas-textPrimary font-mono uppercase tracking-wider">
                    Held-Out Test Performance: {selectedEvaluation.modality.toUpperCase()} ({selectedEvaluation.model_type.replace('_', ' ').toUpperCase()})
                  </h3>
                  <p className="text-[11px] font-mono text-zinc-500">
                    Trained at: {new Date(selectedEvaluation.trained_at).toLocaleString()}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <div className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-emerald-950/40 border border-emerald-800/40 text-emerald-400 text-[11px] font-mono">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Zero-Leakage Group Split Verified</span>
                  </div>
                  {selectedEvaluation.test_metrics.is_calibrated ? (
                    <div className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-purple-950/40 border border-purple-800/40 text-purple-300 text-[11px] font-mono">
                      <span>Calibrated ({selectedEvaluation.test_metrics.calibration_method})</span>
                    </div>
                  ) : (
                    <div className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-zinc-800 border border-zinc-700 text-zinc-400 text-[11px] font-mono">
                      <span>Uncalibrated</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Core Metric Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 font-mono text-xs">
                <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 text-center">
                  <span className="text-[10px] text-zinc-500 block uppercase">Accuracy</span>
                  <span className="text-lg font-bold text-accent">
                    {(selectedEvaluation.test_metrics.accuracy * 100).toFixed(1)}%
                  </span>
                </div>

                <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 text-center">
                  <span className="text-[10px] text-zinc-500 block uppercase">Precision</span>
                  <span className="text-lg font-bold text-zinc-100">
                    {(selectedEvaluation.test_metrics.precision * 100).toFixed(1)}%
                  </span>
                </div>

                <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 text-center">
                  <span className="text-[10px] text-zinc-500 block uppercase">Recall</span>
                  <span className="text-lg font-bold text-zinc-100">
                    {(selectedEvaluation.test_metrics.recall * 100).toFixed(1)}%
                  </span>
                </div>

                <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 text-center">
                  <span className="text-[10px] text-zinc-500 block uppercase">F1-Score</span>
                  <span className="text-lg font-bold text-purple-400">
                    {(selectedEvaluation.test_metrics.f1_score * 100).toFixed(1)}%
                  </span>
                </div>

                <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-3 text-center">
                  <span className="text-[10px] text-zinc-500 block uppercase">ROC-AUC</span>
                  <span className="text-lg font-bold text-emerald-400">
                    {selectedEvaluation.test_metrics.roc_auc !== null
                      ? (selectedEvaluation.test_metrics.roc_auc * 100).toFixed(1) + '%'
                      : 'N/A'}
                  </span>
                </div>
              </div>

              {/* Confusion Matrix Table */}
              <div className="space-y-2">
                <h4 className="text-xs font-mono font-semibold text-zinc-300 uppercase tracking-wider">
                  Test Confusion Matrix ({selectedEvaluation.test_metrics.total_samples} held-out samples)
                </h4>
                <div className="overflow-x-auto rounded border border-canvas-borderSubtle">
                  <table className="w-full text-center font-mono text-xs">
                    <thead className="bg-canvas-elevated text-zinc-400 text-[10px] uppercase">
                      <tr>
                        <th className="py-2 px-3 text-left">Ground Truth</th>
                        <th className="py-2 px-3">Predicted Cover (0)</th>
                        <th className="py-2 px-3">Predicted Stego (1)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-canvas-borderSubtle bg-canvas-elevated/40 text-zinc-200">
                      <tr>
                        <td className="py-2 px-3 text-left font-semibold text-zinc-400">Actual Cover</td>
                        <td className="py-2 px-3 text-emerald-400 font-bold bg-emerald-950/20">
                          TN: {selectedEvaluation.test_metrics.true_negatives}
                        </td>
                        <td className="py-2 px-3 text-red-400 font-bold bg-red-950/20">
                          FP: {selectedEvaluation.test_metrics.false_positives}
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2 px-3 text-left font-semibold text-zinc-400">Actual Stego</td>
                        <td className="py-2 px-3 text-red-400 font-bold bg-red-950/20">
                          FN: {selectedEvaluation.test_metrics.false_negatives}
                        </td>
                        <td className="py-2 px-3 text-emerald-400 font-bold bg-emerald-950/20">
                          TP: {selectedEvaluation.test_metrics.true_positives}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Matched Condition Comparison & Payload Category Breakdown */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* 1. Payload Density Breakdown */}
                <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-4 space-y-2 font-mono text-xs">
                  <span className="text-zinc-300 font-semibold block uppercase text-[11px]">
                    Stego Detection Rate by Payload Size
                  </span>
                  <div className="space-y-1.5 text-[11px]">
                    {Object.entries(selectedEvaluation.test_metrics.by_payload_category).map(([cat, data]) => (
                      <div key={cat} className="flex justify-between items-center py-1 border-b border-zinc-800/60 last:border-0">
                        <span className="capitalize text-zinc-400">{cat} Payload ({data.sample_count} samples):</span>
                        <span className="font-bold text-accent">{(data.stego_detection_rate * 100).toFixed(1)}% Detected</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 2. Matched Strategy Comparison */}
                <div className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-4 space-y-2 font-mono text-xs">
                  <span className="text-zinc-300 font-semibold block uppercase text-[11px]">
                    Matched Strategy Comparison
                  </span>
                  <div className="space-y-1.5 text-[11px]">
                    {Object.entries(selectedEvaluation.test_metrics.by_allocation_strategy).map(([strat, data]) => (
                      <div key={strat} className="flex justify-between items-center py-1 border-b border-zinc-800/60 last:border-0">
                        <span className="capitalize text-zinc-400">{strat} Allocation ({data.sample_count} samples):</span>
                        <span className="font-bold text-purple-400">{(data.stego_detection_rate * 100).toFixed(1)}% Detected</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Academic Limitations Note */}
              <div className="rounded border border-canvas-borderSubtle bg-zinc-900/60 p-3 text-[11px] font-mono text-zinc-400 flex items-start space-x-2">
                <Info className="w-4 h-4 text-accent mt-0.5 flex-shrink-0" />
                <span>{selectedEvaluation.test_metrics.limitations_note}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================= */}
      {/* TAB 3: BENCHMARK DATASET INSPECTOR                        */}
      {/* ========================================================= */}
      {activeTab === 'dataset' && (
        <div className="space-y-6">
          <div className="rounded-lg border border-canvas-border bg-canvas-surface p-5 sm:p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="space-y-0.5">
                <h2 className="text-sm font-semibold text-canvas-textPrimary font-mono uppercase tracking-wider flex items-center space-x-2">
                  <Database className="w-4 h-4 text-emerald-400" />
                  <span>Steganalysis Labeled Benchmark Datasets</span>
                </h2>
                <p className="text-xs text-canvas-textSecondary font-mono">
                  Procedural cover media synthesized with deterministic seeds and corresponding stego derivatives.
                </p>
              </div>

              <button
                type="button"
                onClick={handleGenerateDataset}
                disabled={datasetLoading}
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded text-xs font-mono bg-canvas-elevated hover:bg-zinc-800 border border-canvas-border text-canvas-textSecondary disabled:opacity-40 transition-colors self-start sm:self-auto"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${datasetLoading ? 'animate-spin text-accent' : ''}`} />
                <span>Regenerate Datasets</span>
              </button>
            </div>

            {datasetError && (
              <div className="rounded border border-red-800/40 bg-red-950/20 p-3 text-xs font-mono text-red-300 flex items-start space-x-2">
                <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                <span>{datasetError}</span>
              </div>
            )}

            {/* Modality Dataset Summaries */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              {datasetSummaries.map((ds) => (
                <div key={ds.modality} className="rounded border border-canvas-borderSubtle bg-canvas-elevated p-4 space-y-3 font-mono text-xs">
                  <div className="flex justify-between items-center pb-2 border-b border-canvas-borderSubtle">
                    <span className="font-bold text-zinc-100 uppercase flex items-center space-x-1.5">
                      {ds.modality === 'image' && <ImageIcon className="w-4 h-4 text-accent" />}
                      {ds.modality === 'audio' && <Music className="w-4 h-4 text-emerald-400" />}
                      {ds.modality === 'video' && <VideoIcon className="w-4 h-4 text-purple-400" />}
                      <span>{ds.modality} Dataset</span>
                    </span>
                    <span className="text-[11px] text-accent font-semibold">{ds.total_samples} samples</span>
                  </div>

                  <div className="space-y-1.5 text-[11px] text-zinc-400">
                    <div className="flex justify-between">
                      <span>Cover (Label 0):</span>
                      <span className="text-zinc-200 font-bold">{ds.cover_count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Stego (Label 1):</span>
                      <span className="text-zinc-200 font-bold">{ds.stego_count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Independent Source Groups:</span>
                      <span className="text-zinc-200 font-bold">{ds.sources_count}</span>
                    </div>
                    <div className="flex justify-between border-t border-zinc-800/80 pt-1">
                      <span>Feature Dimensions:</span>
                      <span className="text-zinc-200 font-bold">{ds.feature_count} features</span>
                    </div>
                  </div>

                  <div className="pt-2">
                    <span className="text-[10px] text-zinc-500 block uppercase mb-1">Feature Vectors:</span>
                    <div className="flex flex-wrap gap-1">
                      {ds.feature_names.map((fname) => (
                        <span key={fname} className="text-[9px] bg-zinc-900 border border-zinc-800 px-1.5 py-0.5 rounded text-zinc-400">
                          {fname.replace(/^(img_|aud_|vid_)/, '')}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
