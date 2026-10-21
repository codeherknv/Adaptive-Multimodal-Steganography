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

