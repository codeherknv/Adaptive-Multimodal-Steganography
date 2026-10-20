# Experimental Plan & Benchmarking Protocol

## Phase Roadmap for Experiments
1. **Capacity & Distortion Benchmark**:
   - Evaluate PSNR / MSE for Image across payload sizes (0.01 bpp to 0.4 bpp).
   - Evaluate SNR / MSE for Audio across payload sizes (0.001 bpb to 0.05 bpb).
2. **Recovery Reliability Protocol**:
   - Clean channel test (100% bit recovery expected).
   - Channel noise & mild transcoding checks.
3. **Steganalysis Detection Benchmark**:
   - Generate balanced cover and stego datasets.
   - Extract feature sets and split by source instance (zero-leakage train/test split).
   - Compute Confusion Matrix, ROC-AUC, Precision, Recall, F1 score.
4. **Allocation Strategy Comparison**:
   - Baseline 1: Fixed allocation (e.g. 33% image, 33% audio, 34% video).
   - Strategy 2: Empirical Adaptive allocation based on carrier capacity and distortion tolerance.
