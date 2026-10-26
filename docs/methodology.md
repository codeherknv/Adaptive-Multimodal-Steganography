# Research Methodology & Theoretical Foundations

## 1. Research Goal & Candidate Contribution
To evaluate whether an empirically informed adaptive payload-allocation strategy across multimodal carriers (image, audio, video) can optimize the multi-objective trade-off among:
1. **Payload Capacity** (total bytes embedded safely).
2. **Perceptual Media Quality** (PSNR, SSIM for image/video; SNR for audio).
3. **Channel Recovery Reliability** (extraction integrity after transformations such as light recompression or channel noise).
4. **Steganalytic Undetectability** (empirical ROC-AUC and detection error of baseline classifiers).
5. **Computational Latency** (execution time for embedding and extraction).

---

## 2. Layered Defense-in-Depth Model

The platform structures data protection into three decoupled, complementary layers:

```
[Plaintext Secret]
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ 1. Cryptographic Layer (AES-256-GCM)                  │
│    - Confidentiality (AES-256)                         │
│    - Authenticity & Integrity (128-bit GHASH Tag)       │
│    - Rejection of tampered / forged messages           │
└────────────────────────────────────────────────────────┘
       │ Encrypted Envelope
       ▼
┌────────────────────────────────────────────────────────┐
│ 2. Payload Codec Layer (Binary ASTG Framing)           │
│    - Fixed 34-byte packet header                       │
│    - Partitioning across heterogeneous channels        │
│    - Independent CRC32 checksum per chunk              │
│    - Ordered reassembly & truncation detection         │
└────────────────────────────────────────────────────────┘
       │ Formatted Chunks
       ▼
┌────────────────────────────────────────────────────────┐
│ 3. Multimodal Steganographic Carrier Layer             │
│    - PNG Image Carrier (Spatial LSB)                   │
│    - WAV PCM Audio Carrier (16-bit Sample LSB)         │
│    - Video Carrier (Frame-level embedding)             │
│    - Concealment of transmission existence             │
└────────────────────────────────────────────────────────┘
```

---

## 3. Cryptography vs. Steganography: Why Both Are Essential

- **Cryptography Alone**:
  Encrypts plaintext into high-entropy ciphertext. While computationally infeasible for an adversary to read without the key, ciphertext in transit immediately reveals that confidential communication is occurring, exposing the participants to targeted surveillance or blocking.
- **Steganography Alone**:
  Hides the presence of data within innocuous cover media. However, classical steganography provides no confidentiality if the embedding algorithm is known (Kerckhoffs's principle) and lacks tamper detection if the carrier undergoes channel distortion.
- **Combined (Defense-in-Depth)**:
  1. Steganography conceals the transmission channel.
  2. Authenticated encryption (AES-256-GCM) ensures that even if a machine-learning steganalyzer detects carrier anomalies, the adversary cannot recover the plaintext or inject malicious modifications without triggering an immediate authentication tag failure.

---

## 4. Galois/Counter Mode (GCM) Mathematics & Security

AES-GCM combines counter-mode encryption (CTR) with a Galois field universal hash (GHASH) over GF($2^{128}$):
1. **Encryption**:
   $$\text{Ciphertext } C = P \oplus \text{AES}_K(\text{Nonce} \mathbin{\Vert} \text{Counter})$$
2. **Authentication Tag**:
   $$T = \text{GHASH}_H(\text{AAD} \mathbin{\Vert} C \mathbin{\Vert} \text{Lengths}) \oplus \text{AES}_K(\text{Nonce} \mathbin{\Vert} 1)$$
3. **Catastrophic Failure of Nonce Reuse**:
   If the same key $K$ and nonce $N$ are ever reused for two different messages $P_1$ and $P_2$, the keystream is identical:
   $$C_1 \oplus C_2 = (P_1 \oplus \text{Keystream}) \oplus (P_2 \oplus \text{Keystream}) = P_1 \oplus P_2$$
   Furthermore, an adversary can solve for the GHASH key $H$, completely breaking message authentication for all subsequent communications under that key.
   *Mitigation*: Our engine strictly requires a 96-bit fresh nonce drawn from the operating system's cryptographic entropy source (`os.urandom(12)`) on every invocation.

---

## 5. Codec Integrity vs. Cryptographic Authenticity

Students must distinguish between two levels of data validation:
1. **Codec Integrity (CRC32)**:
   Detects accidental transmission errors (e.g., bit flips from media recompression or truncated carrier uploads) quickly and cheaply before expensive cryptographic operations are performed.
2. **Cryptographic Authenticity (AES-GCM Tag)**:
   Protects against intelligent adversarial tampering. A CRC32 checksum can be trivially forged by an attacker, but an AES-GCM 128-bit authentication tag cannot be forged without the 256-bit secret key.

---

## 6. Spatial Image Steganography & Perceptual Quality Metrics

### 1. Spatial Domain vs. Transform Domain Steganography
- **Spatial LSB**:
  Operates directly on pixel color intensity values $I(x, y, c) \in [0, 255]$ in uncompressed/lossless formats (PNG, BMP). It yields maximum embedding capacity (1 bit per color subpixel) with minimal computational latency $\mathcal{O}(N)$ and virtually imperceptible visual degradation.
- **Vulnerability to Lossy Compression**:
  Because spatial LSB modifies only the least significant bit, any lossy re-encoding (such as JPEG quantization or chroma subsampling) alters pixel values and corrupts embedded bit streams. Lossless PNG carriers are required for reliable recovery in this baseline.

### 2. Length-Prefixed Binary Framing (`PSTG`) vs. Sentinel Markers
Many naive steganographic implementations rely on a sentinel byte sequence (e.g., `0xFF 0xFF 0x00 0x00`) to signal the end of an embedded message:
- **Flaw of Sentinel Framing**: High-entropy encrypted payloads (such as AES-GCM ciphertext) are statistically indistinguishable from pseudorandom noise and have a non-zero probability of containing the sentinel sequence within their body, causing premature extraction truncation.
- **Length-Prefixed Solution**: The 14-byte `PSTG` framing header embeds the exact uint32 payload byte count upfront. The extraction engine reads precisely $14 + L$ bytes (i.e. $(14 + L) \times 8$ carrier bits) and halts, avoiding ambiguous termination markers and out-of-bounds reading.

### 3. Perceptual Quality Metrics & Interpretations
Steganographic quality assessment relies on objective mathematical distortion measures:
1. **MSE (Mean Squared Error)**:
   Quantifies the average energy of the steganographic noise. For 1-bit LSB replacement where payload bits match carrier bits with probability $p \approx 0.5$, the expected MSE across modified subpixels is $\approx 0.5 / (\text{Total Pixels})$.
2. **PSNR (Peak Signal-to-Noise Ratio)**:
   Logarithmic ratio of maximum signal power ($255^2$) to MSE. In academic literature:
   - $\text{PSNR} > 40\text{ dB}$: Distortion is conventionally considered inconspicuous to the human visual system (HVS).
   - $\text{PSNR} > 60\text{ dB}$: High numerical fidelity, typical for low-density spatial LSB steganography.
   - $\text{PSNR} = \infty$: Exact numerical identity ($\text{MSE} = 0$).
3. **SSIM (Structural Similarity Index)**:
   Unlike MSE/PSNR which measure absolute pixel intensity errors, SSIM models the human visual perception of structural information (luminance, contrast, and structure). An SSIM score $> 0.999$ confirms that edge structures and textures are well preserved.

### 4. Image Fidelity vs. Steganalytic Undetectability
A fundamental principle in steganography research is the distinction between **carrier fidelity** and **steganalytic undetectability**:
- **Fidelity Metrics (PSNR & SSIM)**: Measure how closely the stego image mimics the cover image in terms of human perception and raw signal power.
- **Steganalysis Resistance**: Statistical and machine-learning steganalysis tools (e.g., sample pair analysis, Chi-square attacks, SPAM features) do not inspect images visually. Instead, they exploit statistical anomalies caused by LSB flipping (such as imbalances in Pairs of Values / PoVs or pixel co-occurrence matrices).
- **Core Principle**: High PSNR (> 40 dB) is a prerequisite for unobtrusive transmission, but it does **not** guarantee invisibility or prove resistance against steganalysis. Evaluating true detectability requires empirical steganalysis experiments (planned for Phase 8).

---

## 7. PCM Audio Steganography & Distortion Metrics

### 1. Linear PCM Audio Carrier Representation
In uncompressed Pulse Code Modulation (PCM) audio, sound waveforms are sampled at discrete intervals (e.g. 44,100 Hz or 48,000 Hz) and quantized:
- **16-bit Signed Integer (`int16`)**:
  Each sample is represented in two's complement integer notation in $[-32768, 32767]$. Modifying the least significant bit alters the sample by at most $\pm 1$ unit out of $65536$ total quantization steps, corresponding to an amplitude deviation of approximately $-96\text{ dBFS}$.
- **8-bit Unsigned Integer (`uint8`)**:
  Each sample is an unsigned byte in $[0, 255]$ with silence at $128$. LSB modification alters the sample by $\pm 1$ unit out of $256$, corresponding to an amplitude deviation of approximately $-48\text{ dBFS}$.
- **Multi-Channel Interleaving**:
  Stereo WAV files interleave left and right channels ($L_0, R_0, L_1, R_1, \dots$). The engine flattens this interleaved sequence deterministically, ensuring that both stereo channels receive payload bits uniformly across the duration of the recording.

### 2. Audio Binary Framing Header (`WSTG`)
Similar to the image carrier, audio payloads use a length-prefixed 14-byte binary framing header (`b"WSTG"`), encoding:
- `b"WSTG"` (4 bytes magic signature)
- Version 1 (1 byte)
- Reserved (1 byte)
- Payload length $L$ (4 bytes uint32)
- IEEE 802.3 CRC32 checksum (4 bytes uint32)

This header is completely separated from the image `b"PSTG"` header to prevent cross-carrier signature collisions.

### 3. Audio Quality Metrics & Derivations
To objectively evaluate audio distortion, two complementary metrics are implemented:
1. **Normalized Mean Squared Error (MSE)**:
   Normalizing samples to $[-1.0, 1.0]$ prevents metric scale distortion between 8-bit and 16-bit files:
   $$\text{MSE} = \frac{1}{N} \sum_{i=0}^{N-1} (x_i - y_i)^2$$
2. **Signal-to-Noise Ratio (SNR)**:
   Measures the ratio of original cover audio signal energy to the steganographic embedding noise energy:
   $$\text{SNR}_{\text{dB}} = 10 \cdot \log_{10}\left(\frac{\sum_{i=0}^{N-1} x_i^2}{\sum_{i=0}^{N-1} (x_i - y_i)^2}\right)$$
   - When cover and stego audio are identical, error energy is zero; the engine reports $\text{SNR} = \infty$.
   - In 16-bit audio with low payload ratio, SNR typically exceeds $80\text{ dB}$.

### 4. Audio Fidelity vs. Steganalytic Detectability
A critical finding for students and researchers:
- **SNR vs. Inaudibility**: SNR is a purely mathematical ratio of broadband energy. It does not account for the **psychoacoustic human auditory system (HAS)**, which exhibits non-linear frequency sensitivity (Fletcher-Munson equal-loudness contours) and simultaneous/temporal masking thresholds. A distortion that is numerically negligible in high-energy loud passages may be distinctly audible during silent pauses.
- **Audio Steganalysis Attacks**: Classical audio LSB steganography introduces statistical regularities in the audio waveform:
  - **Sample Pair Analysis (SPA)** and **Histogram Attacks**: LSB substitution pairs adjacent even/odd sample values (PoVs), flattening the second-order difference histogram.
  - **Phase & Derivative Discontinuities**: High-frequency spectral analysis can detect artificial high-frequency noise introduced by random LSB replacement.
- **Core Principle**: An SNR exceeding $60\text{ dB}$ confirms high acoustic fidelity, but does **not** prove security against statistical audio steganalysis. Machine-learning audio steganalysis classifiers will be implemented in Phase 8 to empirically quantify detection boundaries.

---

## 8. Frame-Based Video Steganography & Temporal Considerations

### 1. Temporal Extension of Spatial Steganography
Video streams are temporal sequences of discrete 2D image frames:
$$V = [F_0, F_1, F_2, \dots, F_{N-1}], \quad F_i \in \mathbb{R}^{H \times W \times C}$$
The video steganography engine embeds payload bits into the spatial color channels (B, G, R) of frames sequentially. Because video carriers possess high dimensionality ($N \times H \times W \times 3$ subpixels), they offer substantially higher payload capacities than individual static images or short audio clips.

### 2. Lossless Codec Mandate vs. Lossy Video Compression
In academic steganography research, carrier integrity is paramount:
- **Lossy Compression (H.264, H.265, VP9, AV1, MPEG-4)**:
  Consumer video codecs achieve compression ratios exceeding $100:1$ through lossy spatial Discrete Cosine Transform (DCT) quantization, inter-frame motion estimation, and 4:2:0 chroma subsampling. These transformations alter high-frequency pixel variations, completely destroying spatial LSB modifications upon re-encoding.
- **Lossless Codec Standard (FFV1 / HuffYUV)**:
  To prevent silent bit corruption, the platform utilizes FFV1 (Fast Forward Video Codec 1, IETF RFC 9043) or HuffYUV (HFYU) in an AVI/MKV container. These codecs employ predictive intra-frame coding with entropy coding (variable-length Golomb-Rice or range coding), guaranteeing $100\%$ bit-exact sample reconstruction ($MSE = 0.0$ on carrier round-trips).

### 3. Binary Framing Header (`VSTG`)
To guarantee unambiguous extraction without relying on fragile sentinel markers, video payloads are framed with a 14-byte `b"VSTG"` header:
- `b"VSTG"` magic signature (4 bytes)
- Format version 1 (1 byte)
- Reserved (1 byte)
- Declared payload byte length $L$ (4 bytes uint32)
- IEEE 802.3 CRC32 checksum (4 bytes uint32)

Extraction begins at Frame 0, reads exactly 112 bits to parse the header, extracts the declared $L \times 8$ payload bits across frames, and validates the CRC32 checksum before passing the ciphertext to the cryptographic layer.

### 4. Spatial Fidelity vs. Inter-Frame Video Steganalysis
Students must understand the fundamental difference between spatial image steganalysis and temporal video steganalysis:
- **Spatial Metrics (Average MSE & PSNR)**:
  Measure the pixel-level Euclidean distance between cover frames and stego frames. While an average PSNR $> 60\text{ dB}$ confirms high visual fidelity to the human visual system, it models only spatial distortion.
- **Inter-Frame Temporal Steganalysis**:
  Video steganalysts exploit temporal correlations across consecutive frames:
  1. **Optical Flow & Motion Vector Anomalies**: Embedding artificial noise into static background areas alters the statistical distribution of inter-frame residual errors.
  2. **Inter-Frame Difference Histograms**: Natural video exhibits smooth temporal transitions; spatial LSB replacement increases inter-frame variance and decorrelates adjacent frames.
- **Core Principle**: High video PSNR demonstrates spatial transparency, but does **not** prove resistance against temporal video steganalysis. Supervised classification of multimodal steganalytic features will be developed in Phase 8.

---

## 9. Unified Multimodal Allocation & Rate-Distortion Principles (Phase 6)

### 1. The Multimodal Synergistic Hypothesis
In classical steganography, embedding an entire payload into a single medium concentrates embedding distortion into one domain, sharply elevating the relative payload rate (bits-per-pixel or bits-per-sample). Statistical and machine-learning detectors can easily detect the resulting distribution shift.

The core hypothesis of multimodal allocation is that **distributing the payload across heterogeneous carriers reduces detectability**:
$$\text{Global Risk } \mathcal{R} = f\left(\text{Risk}_{\text{image}}(L_{\text{img}}), \text{Risk}_{\text{audio}}(L_{\text{aud}}), \text{Risk}_{\text{video}}(L_{\text{vid}})\right)$$
By partitioning the payload such that each carrier operates at a minimal embedding fraction, the overall anomaly footprint is minimized.

### 2. Carrier Profiling Features
Before allocation, candidate carriers are profiled:
1. **Spatial Laplacian Variance (Image)**:
   $$\sigma^2_{\text{lap}} = \text{Var}(\nabla^2 I)$$
   Evaluates high-frequency texture. Smooth areas (low variance) show high detectability risk; textured regions (high variance) provide greater perceptual and statistical masking.
2. **Acoustic Dynamism & RMS (Audio)**:
   $$\text{RMS} = \sqrt{\frac{1}{N} \sum_{t=1}^N s(t)^2}, \quad \sigma^2_{\Delta s} = \text{Var}(s(t) - s(t-1))$$
   Measures signal energy and dynamic fluctuations. Rapid acoustic transitions mask LSB replacements more effectively than silence or constant sinusoids.
3. **Temporal Motion Variance (Video)**:
   $$\sigma^2_{\text{diff}} = \text{Var}(F_t - F_{t-1})$$
   Evaluates inter-frame motion dynamism. Moving objects and camera motion mask high-frequency pixel variations far better than static scenes.

### 3. Allocation Strategy Formulations
- **Fixed Baseline Strategy**:
  Divides the payload equally across carriers ($L / 3$). If any carrier $k$ has net capacity $M_k < L / 3$, it is clamped to $M_k$, and the deficit is distributed via water-filling to the remaining carriers with headroom.
- **Adaptive Feature-Weighted Strategy**:
  Assigns suitability weights $W_i = \alpha_i \times \sigma_i \times \log_2(1 + M_i)$, allocating bytes proportional to $W_i$, followed by iterative bounded clamping and residual integer remainder distribution.

### 4. Framing Overhead & Capacity Invariants
Every chunk embedded in carrier $i$ requires a 34-byte ASTG packet header. In turn, each carrier module adds its 14-byte carrier frame header (`PSTG`, `WSTG`, `VSTG`).
The maximum payload an envelope can carry in carrier $i$ is strictly:
$$M_i = \max(0, C_i - 34)$$
where $C_i$ is the carrier's usable capacity. Total net multimodal capacity $\sum M_i$ must be $\ge L_{\text{envelope}}$, otherwise the request is safely rejected with `MultimodalCapacityExceededError`.


