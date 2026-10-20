# Research Methodology

## Research Goal
To evaluate whether an empirically informed adaptive payload-allocation strategy across multimodal carriers (image, audio, video) can optimize the multi-objective trade-off among:
1. **Payload Capacity** (total bytes embedded safely).
2. **Perceptual Media Quality** (PSNR, SSIM, Audio SNR).
3. **Channel Recovery Reliability** (extraction integrity after transformations such as light recompression).
4. **Steganalytic Undetectability** (empirical ROC-AUC and detection error of baseline classifiers).
5. **Computational Latency** (execution time for embedding/extracting).

## Steganography vs Cryptography
- **Cryptography** protects the confidentiality of a secret message by transforming it into unintelligible ciphertext. An adversary observing the transmission knows a secret exists.
- **Steganography** conceals the very existence of communication by hiding the ciphertext within an innocuous carrier medium (e.g. image pixels, audio samples, video frames).
- Combining both guarantees defense-in-depth: even if a steganalyzer detects anomalous carrier statistics, authenticated encryption prevents the adversary from reading the secret.
