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
