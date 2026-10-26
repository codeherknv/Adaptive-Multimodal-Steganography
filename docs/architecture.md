# System Architecture & Technical Specifications

## Overview
This platform implements **Reliability-Aware Adaptive Multimodal Steganography with Machine-Learning-Based Steganalysis Across Image, Audio and Video**.

The system strictly decouples the client user interface from the Python-based research and evaluation engine.

```
+---------------------------------------------------------------+
|                        React Frontend                         |
|   (TypeScript, Vite, Tailwind CSS, Lucide React, Recharts)    |
+---------------------------------------------------------------+
                               |
                               | REST API (HTTP / JSON / Multipart)
                               v
+---------------------------------------------------------------+
|                       FastAPI Backend                         |
|           (Pydantic schemas, CORS, Modular Routers)           |
+---------------------------------------------------------------+
                               |
       +-----------------------+------------------------+
       v                                                v
+-----------------------------+          +-----------------------------+
|    Core Research Engine     |          |   Steganalysis & Testing    |
| - AES-256-GCM Cryptography  |          | - Statistical feature ext.  |
| - Packet Header Codec       |          | - Scikit-learn classifier   |
| - Allocation Policies       |          | - ROC-AUC & Confusion Matrix|
| - Media Stego (Img/Aud/Vid) |          | - Quality metrics (PSNR/SNR)|
+-----------------------------+          +-----------------------------+
```

---

## 1. Cryptographic Architecture (AES-256-GCM)

Confidentiality and integrity are enforced using AES-256-GCM (Galois/Counter Mode) via Python's `cryptography` library.

### Principles:
1. **Authenticated Encryption with Associated Data (AEAD)**:
   - Provides both confidentiality and authenticity.
   - Decryption verifies a 128-bit authentication tag before any plaintext bytes are released.
   - If even a single bit of ciphertext, nonce, or metadata is altered, the library raises `InvalidTag`, which our engine maps to a clean `DecryptionError`.
2. **Nonce Freshness**:
   - Exactly 96 bits (12 bytes) per NIST SP 800-38D.
   - A fresh cryptographically secure random nonce is generated via `os.urandom(12)` for every single encryption operation.
   - *Critical Warning for Students*: Nonce reuse in GCM completely compromises both authenticity and confidentiality. Nonces must never repeat for a given key.
3. **Encrypted Envelope Layout (Version 1)**:
   ```
   +-------------------+--------------------+-------------------+------------------------------+
   | Version (1 byte)  | Reserved (1 byte)  | Nonce (12 bytes)  | Ciphertext + Auth Tag (N+16) |
   +-------------------+--------------------+-------------------+------------------------------+
   ```
   - Total header: 14 bytes (`0x01` + `0x00` + 12-byte nonce).
   - The first 2 bytes (`version + reserved`) are passed as Additional Authenticated Data (AAD) into AES-GCM, preventing header tampering.
   - Minimum envelope size: 30 bytes (for a 0-byte plaintext message).

### Key Management Workflow:
- **Random 256-bit Key**: Generated via `os.urandom(32)`. Returned separately to the user in Base64 or Hex encoding.
- **Passphrase Derivation (PBKDF2)**: Implements PBKDF2-HMAC-SHA256 with 600,000 iterations (OWASP recommendation) and a fresh 16-byte random salt.
- **Key Hygiene**: Keys are **never** stored inside media carriers or committed to Git. Anyone possessing the key can decrypt the secret.

---

## 2. Versioned Binary Payload Codec (`payload_codec.py`)

When secret data is distributed across heterogeneous carrier media (image, audio, video), each carrier embeds a structured binary chunk.

### Binary Header Specification (34 Bytes, Big-Endian):
```
+--------------------+----------------+-----------------+--------------------------------------+
| Field              | Size / Type    | Byte Offset     | Description                          |
+--------------------+----------------+-----------------+--------------------------------------+
| Magic Signature    | 4 bytes        | 0 - 3           | Fixed ASCII b"ASTG"                  |
| Format Version     | 1 byte uint8   | 4               | 0x01                                 |
| Reserved           | 1 byte uint8   | 5               | 0x00                                 |
| Message Identifier | 16 bytes       | 6 - 21          | 128-bit UUID (groups related chunks) |
| Chunk Index        | 2 bytes uint16 | 22 - 23         | 0-indexed position (0 <= i < Total)  |
| Total Chunks       | 2 bytes uint16 | 24 - 25         | Total chunk count (N >= 1)           |
| Payload Length (L) | 4 bytes uint32 | 26 - 29         | Exact byte length of chunk payload   |
| Payload CRC32      | 4 bytes uint32 | 30 - 33         | IEEE 802.3 CRC32 of chunk payload    |
+--------------------+----------------+-----------------+--------------------------------------+
| Chunk Payload      | L bytes        | 34 - (34+L-1)   | Raw chunk bytes                      |
+--------------------+----------------+-----------------+--------------------------------------+
```

### Chunk Validation & Reassembly Rules:
1. **Header Validation**:
   - Must match magic signature `b"ASTG"` (`InvalidMagicError`).
   - Must match format version `1` (`UnsupportedVersionError`).
   - `total_chunks` must be `>= 1` (`InvalidChunkCountError`).
   - `chunk_index` must be `< total_chunks` (`InvalidChunkIndexError`).
2. **Integrity & Bounds Validation**:
   - `len(data) >= 34 + payload_length` (`TruncatedChunkError`).
   - CRC32 of payload must match header CRC32 (`ChecksumMismatchError`).
   - Disallow trailing bytes unless explicitly allowed (`MalformedChunkError`).
3. **Reassembly Guarantees**:
   - All chunks must share the identical 16-byte `message_id` (`MessageIdMismatchError`).
   - All chunks must declare the same `total_chunks` (`ChunkCountMismatchError`).
   - No duplicate chunk indices allowed (`DuplicateChunkError`).
   - All indices from `0` to `total_chunks - 1` must be present (`MissingChunkError`).
   - Chunks can arrive in any order; the codec deterministically sorts them by index before concatenation.
4. **Distinction from Secret Sharing**:
   - Chunk splitting distributes bytes; it does **not** provide threshold secret sharing (e.g. Shamir's Secret Sharing) or Forward Error Correction (FEC). Every chunk is required for reconstruction.

---

## 3. Cryptographic API Endpoints

### 1. `POST /api/crypto/encrypt`
- **Request Body**:
  ```json
  {
    "plaintext": "Confidential message",
    "key": "Optional base64 or hex 32-byte key",
    "password": "Optional password for PBKDF2 derivation",
    "salt": "Optional salt for PBKDF2 derivation",
    "encoding": "base64"
  }
  ```
- **Response Body**:
  ```json
  {
    "key": "32-byte key in requested encoding",
    "key_encoding": "base64",
    "salt": null,
    "envelope_version": 1,
    "nonce": "12-byte nonce",
    "ciphertext": "Ciphertext with 16-byte tag",
    "envelope": "Full serialized binary envelope",
    "envelope_bytes_length": 51,
    "plaintext_bytes_length": 21,
    "warning": "Educational Key Workflow: Keep this key separate from carrier media."
  }
  ```

### 2. `POST /api/crypto/decrypt`
- **Request Body**:
  ```json
  {
    "envelope": "Serialized binary envelope string",
    "key": "32-byte key",
    "password": "Password if PBKDF2 used",
    "salt": "Salt if PBKDF2 used",
    "encoding": "base64"
  }
  ```
- **Response Body**:
  ```json
  {
    "plaintext": "Confidential message",
    "authenticated": true,
    "envelope_version": 1,
    "plaintext_bytes_length": 21
  }
  ```

---

## 4. Image Steganography Architecture (`image_stego.py`)

Spatial Least Significant Bit (LSB) steganography is implemented for lossless PNG carrier media using Pillow and NumPy.

### 1. Carrier Processing & Channel Selection:
- **Format Constraint**: PNG (lossless deflate compression). Lossy formats such as JPEG will destroy LSB modifications during discrete cosine transform quantization and are rejected.
- **Color Mode Handling**:
  - `RGB` images: All 3 channels (`R, G, B`) are utilized for embedding.
  - `RGBA` images: Only the first 3 color channels (`[:, :, :3]`) are modified. The Alpha channel (`channel 3`) is strictly preserved untouched to prevent unintended transparency artifacts.
  - `L` (Grayscale): Converted to RGB or processed according to single-channel conventions.

### 2. Binary Framing Header Specification (`PSTG`, 14 Bytes, Big-Endian):
To prevent relying on ambiguous EOF markers or trailing sentinel byte sequences (which can collide with pseudorandom ciphertext), each image embeds a structured 14-byte binary header:

```
+--------------------+----------------+-----------------+------------------------------------+
| Field              | Size / Type    | Byte Offset     | Description                        |
+--------------------+----------------+-----------------+------------------------------------+
| Magic Signature    | 4 bytes        | 0 - 3           | Fixed ASCII b"PSTG"                |
| Format Version     | 1 byte uint8   | 4               | 0x01                               |
| Reserved           | 1 byte uint8   | 5               | 0x00                               |
| Payload Length (L) | 4 bytes uint32 | 6 - 9           | Exact byte length of inner payload |
| Payload CRC32      | 4 bytes uint32 | 10 - 13         | IEEE 802.3 CRC32 of inner payload  |
+--------------------+----------------+-----------------+------------------------------------+
| Inner Payload Data | L bytes        | 14 - (14+L-1)   | Encrypted ASTG envelope or chunk   |
+--------------------+----------------+-----------------+------------------------------------+
```

### 3. Bit Embedding & Extraction Convention:
- **Ordering**: Row-major, column-major, channel-major (`Red`, then `Green`, then `Blue`).
- **Bit Packing**: Most-significant-bit first (MSB-to-LSB, bit 7 down to bit 0) per byte.
- **Carrier Modification**:
  $$\text{pixel}' = (\text{pixel} \mathbin{\&} \text{0xFE}) \mathbin{|} \text{bit}$$
  *(Implemented using `np.uint8(0xFE)` to prevent integer underflow in NumPy 2.x).*
- **Capacity Formula**:
  $$\text{Max Usable Payload Bytes} = \left\lfloor \frac{H \times W \times 3}{8} \right\rfloor - 14$$

---

## 5. Distortion & Perceptual Quality Metrics (`quality_metrics.py`)

To quantify image alteration after steganographic embedding, the evaluation engine implements three standard objective metrics:

1. **Mean Squared Error (MSE)**:
   $$\text{MSE} = \frac{1}{H \times W \times C} \sum_{y=0}^{H-1} \sum_{x=0}^{W-1} \sum_{c=0}^{C-1} [I_1(y, x, c) - I_2(y, x, c)]^2$$
   Measures average squared pixel intensity difference. $\text{MSE} = 0.0$ indicates identical images.

2. **Peak Signal-to-Noise Ratio (PSNR)**:
   $$\text{PSNR} = 10 \cdot \log_{10}\left(\frac{\text{MAX}_I^2}{\text{MSE}}\right) = 20 \cdot \log_{10}\left(\frac{255}{\sqrt{\text{MSE}}}\right)$$
   - Expressed in decibels (dB). Higher values denote less distortion.
   - For identical images ($\text{MSE} = 0$), the implementation returns `math.inf` (rendered as `null` in JSON per RFC 8259).
   - In spatial 1-bit LSB steganography, typical PSNR values exceed $50\text{ dB}$, indicating high visual fidelity.
   - **Critical Research Note**: High PSNR (> 40 dB) and high SSIM (≈ 1.0) measure visual similarity relative to the cover carrier. They do **not** guarantee invisibility or prove resistance to statistical or machine-learning steganalysis (e.g. sample pair analysis, SPAM feature classification), which exploit higher-order statistical artifacts.

3. **Structural Similarity Index Measure (SSIM)**:
   $$\text{SSIM}(x, y) = \frac{(2\mu_x\mu_y + C_1)(2\sigma_{xy} + C_2)}{(\mu_x^2 + \mu_y^2 + C_1)(\sigma_x^2 + \sigma_y^2 + C_2)}$$
   Evaluates luminance, contrast, and structural correlation. Returns a float in $[-1.0, 1.0]$, where $1.0$ represents identical structural appearance. Like PSNR, SSIM measures image fidelity, not steganalytic security.

---

## 6. Image Steganography API Endpoints

### 1. `POST /api/image/capacity`
- **Request**: Multipart form data with `image` (PNG file).
- **Response**:
  ```json
  {
    "width": 512,
    "height": 512,
    "channels": 3,
    "color_mode": "RGB",
    "embeddable_channels_per_pixel": 3,
    "total_carrier_bits": 786432,
    "total_carrier_bytes": 98304,
    "header_overhead_bytes": 14,
    "max_usable_payload_bytes": 98290
  }
  ```

### 2. `POST /api/image/embed`
- **Request**: Multipart form data:
  - `image`: Cover PNG carrier file.
  - `envelope`: Encrypted envelope string.
  - `encoding`: `"base64"` or `"hex"` (default: `"base64"`).
- **Response**:
  ```json
  {
    "status": "success",
    "stego_image_data_url": "data:image/png;base64,iVBORw0KG...",
    "payload_bytes": 51,
    "carrier_bytes_used": 520,
    "capacity_utilization_percent": 0.052,
    "quality_metrics": {
      "mse": 0.00066,
      "psnr": 79.93,
      "ssim": 0.99999
    }
  }
  ```

### 3. `POST /api/image/extract`
- **Request**: Multipart form data:
  - `image`: Stego PNG carrier file.
  - `encoding`: `"base64"` or `"hex"` (default: `"base64"`).
- **Response**:
  ```json
  {
    "status": "success",
    "envelope_data": "<EXTRACTED_ENVELOPE_STRING>",
    "encoding": "base64",
    "payload_bytes": 51,
    "framing_version": 1,
    "crc32_verified": true
  }
  ```

---

## 7. PCM WAV Audio Steganography Architecture

The audio steganography engine (`backend/app/media/audio_stego.py`) implements least-significant-bit (LSB) substitution for uncompressed Linear PCM WAV audio files.

### 1. Carrier Audio Format & Sample Representation
- **Supported Formats**: Uncompressed RIFF/WAVE containers with standard PCM formatting (`WAVE_FORMAT_PCM = 0x0001`).
- **Sample Bit Depths**:
  - **16-bit Signed PCM (`int16`)**: Samples in range $[-32768, 32767]$. LSB substitution modifies the least significant bit:
    $$\text{stego\_sample} = (\text{sample} \ \& \ \sim 1) \ | \ \text{bit}$$
    In two's complement integer representation, clearing the least significant bit with bitwise-AND using `~1` (`-2` or `0xFFFE`) works symmetrically across positive and negative values without integer overflow.
  - **8-bit Unsigned PCM (`uint8`)**: Samples in range $[0, 255]$ with midpoint at $128$. LSB substitution:
    $$\text{stego\_sample} = (\text{sample} \ \& \ \text{0xFE}) \ | \ \text{bit}$$
- **Multi-Channel Interleaving**:
  For multi-channel audio (e.g. stereo, 2 channels), WAV audio frames are stored interleaved:
  $$[L_0, R_0, L_1, R_1, L_2, R_2, \dots, L_{N-1}, R_{N-1}]$$
  The engine flattens the interleaved sample array deterministically into a 1D sequence of samples, embedding sequentially across time and channels. This maximizes capacity while preserving identical frame counts, sample rates, channel configurations, and playback duration.

### 2. Audio Binary Framing Header (`WSTG`)
To strictly separate audio steganographic carriers from image carriers, audio payloads use a distinct 14-byte binary framing header:

```
+--------------------+----------------+-----------------+----------------------------------------+
| Field              | Size / Type    | Byte Offset     | Description                            |
+--------------------+----------------+-----------------+----------------------------------------+
| Magic Signature    | 4 bytes        | 0 - 3           | Fixed ASCII b"WSTG" (WAV Stego)        |
| Format Version     | 1 byte uint8   | 4               | 0x01                                   |
| Reserved           | 1 byte uint8   | 5               | 0x00                                   |
| Payload Length (L) | 4 bytes uint32 | 6 - 9           | Exact byte length of embedded envelope |
| Payload CRC32      | 4 bytes uint32 | 10 - 13         | IEEE 802.3 CRC32 of embedded payload   |
+--------------------+----------------+-----------------+----------------------------------------+
| Embedded Payload   | L bytes        | 14 - (14+L-1)   | AES-256-GCM encrypted envelope bytes  |
+--------------------+----------------+-----------------+----------------------------------------+
```

Total framing overhead is 14 bytes (112 bits). Extraction reads exactly 112 bits, validates `b"WSTG"`, checks the declared length against the total sample count, extracts $L \times 8$ payload bits, and verifies the CRC32 checksum before passing the bytes to the cryptographic layer.

---

## 8. Audio Quality Distortion Metrics

To quantify acoustic alteration after steganographic embedding, the evaluation engine (`backend/app/evaluation/quality_metrics.py`) implements:

1. **Normalized Mean Squared Error (MSE)**:
   PCM samples are normalized to the standard floating-point audio range $[-1.0, 1.0]$:
   - For 16-bit audio: $x_i = \text{sample}_i / 32768.0$
   - For 8-bit audio: $x_i = (\text{sample}_i - 128.0) / 128.0$
   $$\text{MSE} = \frac{1}{N} \sum_{i=0}^{N-1} (x_i - y_i)^2$$
   where $x_i$ is the cover sample and $y_i$ is the stego sample. $\text{MSE} = 0.0$ indicates identical audio.

2. **Signal-to-Noise Ratio (SNR)**:
   $$\text{SNR} = 10 \cdot \log_{10}\left(\frac{P_{\text{signal}}}{P_{\text{noise}}}\right) = 10 \cdot \log_{10}\left(\frac{\sum_{i=0}^{N-1} x_i^2}{\sum_{i=0}^{N-1} (x_i - y_i)^2}\right)$$
   - Expressed in decibels (dB). Higher values denote less audible degradation.
   - For identical audio ($P_{\text{noise}} = 0$), the implementation returns `math.inf` (rendered as `"Infinity"` in JSON and UI).
   - In 16-bit PCM 1-bit LSB steganography, SNR typically exceeds $80\text{ dB}$, representing near-perfect numerical fidelity.
   - **Critical Research Note**: Audio SNR quantifies physical sample-level deviation. It does **not** guarantee absolute inaudibility (which is governed by psychoacoustic frequency masking thresholds) and does **not** prove resistance against audio steganalysis (e.g. sample pair analysis, derivative histogram analysis), which detects artificial LSB smoothing.

---

## 9. Audio Steganography API Endpoints

### 1. `POST /api/audio/capacity`
- **Request**: Multipart form data with `audio` (PCM WAV file).
- **Response**:
  ```json
  {
    "num_channels": 2,
    "channel_layout": "stereo",
    "sample_rate": 44100,
    "sample_width": 2,
    "bits_per_sample": 16,
    "num_frames": 44100,
    "duration_seconds": 1.0,
    "total_samples": 88200,
    "total_carrier_bits": 88200,
    "total_carrier_bytes": 11025,
    "header_overhead_bytes": 14,
    "max_usable_payload_bytes": 11011
  }
  ```

### 2. `POST /api/audio/embed`
- **Request**: Multipart form data:
  - `audio`: Cover PCM WAV carrier file.
  - `envelope`: Encrypted envelope string.
  - `encoding`: `"base64"` or `"hex"` (default: `"base64"`).
- **Response**:
  ```json
  {
    "stego_audio_data_url": "data:audio/wav;base64,UklGR...",
    "filename": "stego_carrier.wav",
    "embedded_bytes": 110,
    "metrics": {
      "mse": 0.00000000,
      "snr": 103.51,
      "snr_display": "103.51 dB",
      "embedded_bytes": 110,
      "framed_bytes": 124,
      "capacity_used_ratio": 0.0112,
      "bits_per_sample_used": 0.0112
    },
    "message": "Payload successfully embedded into WAV audio using sample LSB."
  }
  ```

### 3. `POST /api/audio/extract`
- **Request**: Multipart form data:
  - `audio`: Stego PCM WAV carrier file.
  - `encoding`: `"base64"` or `"hex"` (default: `"base64"`).
- **Response**:
  ```json
  {
    "envelope": "<EXTRACTED_ENVELOPE_STRING>",
    "encoding": "base64",
    "envelope_bytes_length": 110,
    "envelope_version": 1,
    "status": "verified",
    "message": "Successfully extracted and verified authenticated envelope from WAV carrier."
  }
  ```

---

## 10. Frame-Based Video Steganography Architecture

The video steganography engine (`backend/app/media/video_stego.py`) implements multi-frame spatial least-significant-bit (LSB) embedding and extraction across video frames using OpenCV (`cv2`) and lossless video codecs.

### 1. Carrier Video Format & Lossless Codec Selection
- **Lossless Codec Imperative**:
  Lossy video compression (such as H.264/AVC, H.265/HEVC, VP9, AV1, or MPEG-4) applies lossy transform quantization (DCT), motion compensation prediction errors, and chroma subsampling (4:2:0). These operations alter raw pixel values across frames, completely corrupting spatial LSB modifications.
  The engine dynamically discovers operational lossless codecs on the host system:
  1. **FFV1 (Fast Forward Video Codec 1)**: IETF RFC 9043 lossless intra/inter-frame video codec. Encoded in an AVI (`.avi`) or Matroska (`.mkv`) container.
  2. **HuffYUV (HFYU)**: Lossless Huffman-coded YUV/RGB video codec.
- **Dynamic Codec Negotiation**:
  The system probes `cv2.VideoWriter` capabilities upon initialization (`detect_available_lossless_codec()`). If no operational lossless encoder is available in OpenCV, the engine raises `CodecUnavailableError` rather than silently producing corrupted or lossy output.

### 2. Video Binary Framing Header (`VSTG`)
To maintain strict separation between media carriers, video payloads use a distinct 14-byte binary framing header:

```
+--------------------+----------------+-----------------+----------------------------------------+
| Field              | Size / Type    | Byte Offset     | Description                            |
+--------------------+----------------+-----------------+----------------------------------------+
| Magic Signature    | 4 bytes        | 0 - 3           | Fixed ASCII b"VSTG" (Video Stego)      |
| Format Version     | 1 byte uint8   | 4               | 0x01                                   |
| Reserved           | 1 byte uint8   | 5               | 0x00                                   |
| Payload Length (L) | 4 bytes uint32 | 6 - 9           | Exact byte length of embedded envelope |
| Payload CRC32      | 4 bytes uint32 | 10 - 13         | IEEE 802.3 CRC32 of embedded payload   |
+--------------------+----------------+-----------------+----------------------------------------+
| Embedded Payload   | L bytes        | 14 - (14+L-1)   | AES-256-GCM encrypted envelope bytes  |
+--------------------+----------------+-----------------+----------------------------------------+
```

### 3. Multi-Frame Sequential Embedding Algorithm
1. The video stream is decoded into a sequence of $F$ color frames of resolution $W \times H \times 3$ (BGR channels).
2. The framed bitstream (112 header bits $+ L \times 8$ payload bits) is flattened into a 1D sequence of bits.
3. Bits are substituted into the least significant bit of color channels starting at Frame 0, Row 0, Column 0, Channel 0:
   $$\text{stego\_pixel} = (\text{cover\_pixel} \ \& \ \text{0xFE}) \ | \ \text{bit}$$
4. Once all bits are embedded, any remaining frames in the video container remain **100% bit-exact and unaltered**.
5. The container parameters (frame width, height, frame rate, and total frame count) are strictly preserved.

---

## 11. Video Quality Distortion Metrics

To quantify spatial alteration across the video stream, the evaluation engine (`backend/app/evaluation/quality_metrics.py`) implements:

1. **Average Frame Mean Squared Error (MSE)**:
   $$\text{MSE}_f = \frac{1}{H \times W \times C} \sum_{y=0}^{H-1} \sum_{x=0}^{W-1} \sum_{c=0}^{C-1} [I_1(y, x, c) - I_2(y, x, c)]^2$$
   $$\text{Average MSE} = \frac{1}{F} \sum_{f=0}^{F-1} \text{MSE}_f$$
2. **Average Frame Peak Signal-to-Noise Ratio (PSNR)**:
   $$\text{PSNR} = 10 \cdot \log_{10}\left(\frac{255^2}{\text{Average MSE}}\right)$$
   - Expressed in decibels (dB). For low payload densities, PSNR typically exceeds $60\text{ dB}$.
   - For identical videos ($\text{MSE} = 0$), the implementation returns `math.inf` (displayed as `"Infinity (Identical)"`).
   - **Critical Research Note**: Frame MSE and PSNR measure spatial pixel-level fidelity relative to the cover video. They do **not** guarantee resistance against temporal or inter-frame video steganalysis (e.g. motion vector distribution analysis, inter-frame difference statistics), which will be investigated in Phase 8.

---

## 12. Video Steganography API Endpoints

### 1. `POST /api/video/capacity`
- **Request**: Multipart form data with `video` (AVI, MKV, MP4 file).
- **Response**:
  ```json
  {
    "width": 80,
    "height": 60,
    "channels_per_frame": 3,
    "num_frames": 5,
    "fps": 25.0,
    "duration_seconds": 0.2,
    "total_carrier_bits": 72000,
    "total_carrier_bytes": 9000,
    "header_overhead_bytes": 14,
    "max_usable_payload_bytes": 8986,
    "recommended_codec": "FFV1",
    "container_format": "AVI"
  }
  ```

### 2. `POST /api/video/embed`
- **Request**: Multipart form data:
  - `video`: Cover video carrier file.
  - `envelope`: Encrypted envelope string.
  - `encoding`: `"base64"` or `"hex"` (default: `"base64"`).
- **Response**:
  ```json
  {
    "stego_video_data_url": "data:video/avi;base64,Uk...",
    "preview_frame_data_url": "data:image/png;base64,iV...",
    "filename": "stego_carrier.avi",
    "embedded_bytes": 121,
    "metrics": {
      "average_mse": 0.007611,
      "average_psnr": 69.32,
      "psnr_display": "69.32 dB",
      "total_frames": 5,
      "modified_frames": 1,
      "embedded_bytes": 121,
      "framed_bytes": 135,
      "capacity_used_ratio": 0.015,
      "width": 80,
      "height": 60,
      "fps": 25.0,
      "duration_seconds": 0.2
    },
    "message": "Payload successfully embedded into video frames using spatial LSB."
  }
  ```

### 3. `POST /api/video/extract`
- **Request**: Multipart form data:
  - `video`: Stego video carrier file.
  - `encoding`: `"base64"` or `"hex"` (default: `"base64"`).
- **Response**:
  ```json
  {
    "envelope": "<EXTRACTED_ENVELOPE_STRING>",
    "encoding": "base64",
    "envelope_bytes_length": 121,
    "envelope_version": 1,
    "status": "verified",
    "message": "Successfully extracted and verified authenticated envelope from video carrier."
  }
  ```

---

## 6. Multimodal Allocation & Orchestration Engine (Phase 6)

Phase 6 introduces unified cross-modal coordination across Image, Audio, and Video carriers, implemented in `backend/app/allocation/`:

### A. Carrier Profiling (`profiler.py`):
Calculates exact usable capacities and domain complexity metrics:
- **Image**: Dimensions ($W \times H$), Laplacian variance $\sigma^2_{\text{lap}}$, pixel intensity mean/std, edge density.
- **Audio**: Sample rate, bit depth, channels, duration, RMS energy, sample-difference variance.
- **Video**: Resolution, frame count, FPS, duration, inter-frame difference variance, keyframe Laplacian variance.

### B. Allocation Strategies (`allocator.py`):
1. **Fixed Baseline Strategy**: Strives for equal (1/3 each) payload distribution across available carriers. If a carrier's net capacity is less than its share, it is clamped to capacity, and the overflow is redistributed to remaining carriers with headroom (water-filling).
2. **Adaptive Feature-Weighted Strategy**: Computes a Steganographic Suitability Weight $W_i = \alpha_i \times \sigma_i \times \log_2(1 + \text{Cap}_i)$ based on measured media entropy and capacity. Distributes more bytes to complex, high-entropy carriers with greater capacity while strictly enforcing capacity limits.

### C. Capacity & Overhead Accounting Invariant:
For carrier $i \in \{\text{image}, \text{audio}, \text{video}\}$:
$$\text{Carrier Total Usable Capacity } C_i = \max(0, \text{RawBytes}_i - 14)$$
$$\text{Carrier Net Envelope Payload Capacity } M_i = \max(0, C_i - 34)$$
The 34-byte reduction accounts for the ASTG packet framing header.
A payload of length $L$ can be embedded if and only if $\sum_{i=1}^3 M_i \ge L$.

### D. Unified Orchestration (`engine.py`):
- **Embedding**: Encrypts plaintext via AES-256-GCM $\to$ profiles carriers $\to$ allocates slices $\to$ creates 3 ASTG chunks $\to$ embeds into PNG (`PSTG`), WAV (`WSTG`), and AVI (`VSTG`) $\to$ generates non-secret `manifest.json` $\to$ packages all carriers into `stego_multimodal_bundle.zip`.
- **Extraction**: Unpacks ZIP (or accepts 3 individual carriers) $\to$ extracts chunks $\to$ validates ASTG headers and CRC32 $\to$ checks UUID matching and total chunks $\to$ reassembles original envelope $\to$ decrypts via AES-256-GCM $\to$ returns verified plaintext.

---

## 7. Multimodal API Endpoints (Phase 6)

### 1. `POST /api/multimodal/analyze`
- **Request**: Multipart form data with `image`, `audio`, `video`, and optional `payload_length`, `strategy`.
- **Response**: Comprehensive profiles for all 3 carriers, total usable capacity, capacity shares, and optional simulated allocation.

### 2. `POST /api/multimodal/embed`
- **Request**: Multipart form data with `message`, `image`, `audio`, `video`, `strategy` (`adaptive` or `fixed`), and optional `password` or `key`.
- **Response**: `zip_bundle_data_url` (downloadable ZIP with all 3 stego carriers + manifest), `key`, `salt`, `message_id`, `allocations`, `metrics`, and first-frame video preview.

### 3. `POST /api/multimodal/extract`
- **Request**: Multipart form data with `bundle_zip` (OR individual `image`, `audio`, `video`), and `key` or `password` (+ `salt`).
- **Response**: `plaintext`, `message_id`, `chunk_count` (3), `chunk_sizes`, `verified: true`.

---

## 8. Machine-Learning Steganalysis & Detectability Engine (Phase 7)

Phase 7 introduces machine-learning-based steganalysis detectors and a zero-data-leakage benchmark evaluation pipeline, located in `backend/app/steganalysis/`:

### A. Statistical & Signal Feature Extraction (`features.py`)
Extracts first- and higher-order statistical artifacts that signal LSB modification:

1. **Image Modality (10 Features)**:
   - `img_lsb_one_ratio`: Ratio of 1s in the LSB plane (diverges from cover baseline toward 0.5 under encrypted ciphertext).
   - `img_pov_asymmetry`: Pairs of Values (PoV) asymmetry $|N(2k) - N(2k+1)| / (N(2k) + N(2k+1))$ across color channels.
   - `img_horiz_diff_var`, `img_vert_diff_var`: Sample variance of horizontal and vertical spatial adjacent pixel differences.
   - `img_diff_kurtosis`: Excess kurtosis of spatial differences (LSB replacement flattens the distribution peak).
   - `img_highpass_residual_var`: Variance after applying a $3 \times 3$ Laplacian high-pass filter.
   - `img_lsb_transition_rate`: Frequency of adjacent bit-flips along raster order in the LSB plane.
   - `img_channel_diff_rg`, `img_channel_diff_gb`, `img_channel_diff_br`: Inter-channel covariance differences across color planes.

2. **Audio Modality (8 Features)**:
   - `aud_lsb_one_ratio`: Ratio of 1s in the 16-bit PCM sample LSB plane.
   - `aud_pov_asymmetry`: Sample amplitude pair asymmetry.
   - `aud_first_diff_var`, `aud_second_diff_var`: First and second order temporal difference variances.
   - `aud_diff_kurtosis`: Sample difference kurtosis.
   - `aud_highband_energy_ratio`: Ratio of high-frequency spectral energy to total acoustic energy.
   - `aud_rms_energy`: Normalized root-mean-square audio energy.
   - `aud_zero_crossing_rate`: Normalized zero-crossing rate of the audio waveform.

3. **Video Modality (7 Features)**:
   - `vid_lsb_one_ratio`: Average LSB 1-ratio across all sample frames.
   - `vid_interframe_diff_var`: Variance of frame-to-frame pixel differences $(F_t - F_{t-1})$.
   - `vid_interframe_diff_kurt`: Kurtosis of inter-frame residual errors.
   - `vid_interframe_lsb_flip_rate`: Fraction of corresponding spatial pixels whose LSB toggles between consecutive frames.
   - `vid_spatial_diff_var`: Intra-frame spatial horizontal difference variance averaged across frames.
   - `vid_spatial_diff_kurt`: Intra-frame difference kurtosis.
   - `vid_motion_energy`: Mean absolute frame-to-frame pixel difference.

### B. Benchmark Dataset Generator & Zero-Leakage Splitting (`dataset_generator.py`)
- **Procedural Synthesizers**: Deterministically generates diverse synthetic cover media (textures, gradients, sine chirps, moving geometric patterns).
- **Label 0 (Cover)**: Original clean media instance with zero embedded payload.
- **Label 1 (Stego)**: Stego media containing AES-256-GCM encrypted ASTG payload across Low (10%), Medium (35%), and High (55%) capacity fractions and Fixed vs Adaptive allocation strategies.
- **Strict `source_id` Isolation**: Every base cover is assigned a persistent unique identifier (`img_src_001`). All stego derivatives share the identical `source_id`.
- **Zero-Secret Guarantee**: Plaintext messages, symmetric encryption keys, and nonces are **never** stored in feature matrices or dataset records.

### C. Leak-Free Model Training (`trainer.py`)
- **GroupShuffleSplit**: Splits samples into training and testing partitions strictly grouped by `source_id`. Zero overlap between `train_sources` and `test_sources` is verified by runtime assertion.
- **Preprocessing Isolation**: `StandardScaler` is fitted solely on `X_train` (`scaler.fit(X_train)`) and then applied to `X_test` via `scaler.transform(X_test)`.
- **Model Baselines**:
  - `RandomForestClassifier`: 100 estimators, max depth 6. Provides non-linear boundaries and feature importance rankings.
  - `LogisticRegression`: L2-regularized linear model with balanced class weighting. Provides explainable linear decision boundaries.
- **Evaluation Metrics**: Accuracy, Precision, Recall, F1-Score, ROC-AUC, 2x2 Confusion Matrix, and conditional detection breakdowns by payload category and allocation strategy.
- **Persistence**: Fitted pipelines (`TrainedSteganalyzer`) are serialized to `outputs/models/{modality}_{model_type}.joblib`.

### D. Single-File Live Inference (`classifier.py`)
- Inspects uploaded files, identifies modality (PNG, WAV, AVI), extracts features, scores probability via the trained model, and includes explicit academic disclaimers.

---

## 9. Steganalysis API Endpoints (Phase 7)

### 1. `POST /api/steganalysis/dataset/generate`
- **Request**:
  ```json
  {
    "modality": "image",
    "num_sources": 10,
    "payload_fractions": [0.10, 0.35, 0.55],
    "allocation_strategies": ["fixed", "adaptive"]
  }
  ```
- **Response**: Dataset summary including total samples, class distribution (Cover vs Stego), feature names, and source group counts.

### 2. `GET /api/steganalysis/dataset/summary`
- **Response**: Sample count breakdown for image, audio, and video datasets stored in the active cache.

### 3. `POST /api/steganalysis/train`
- **Request**:
  ```json
  {
    "modality": "image",
    "model_type": "random_forest",
    "test_size": 0.30
  }
  ```
- **Response**: Full `test_metrics` (accuracy, precision, recall, f1, roc_auc, confusion matrix, breakdown by payload category and allocation strategy), model artifact path, train/test source group counts.

### 4. `GET /api/steganalysis/models`
- **Response**: List of trained and persisted model checkpoints on disk with training metadata and evaluation summaries.

### 5. `POST /api/steganalysis/classify`
- **Request**: Multipart form data with `file` (PNG, WAV, or AVI) and optional `model_type` (`random_forest` or `logistic_regression`).
- **Response**: `predicted_label` (0 or 1), `predicted_class` ("Cover" or "Stego"), `stego_probability` (0.0 to 1.0), `confidence_percentage`, full dictionary of extracted numerical features, and scientific disclaimer notice.

---

## 10. Test Execution & Verification

To execute the complete automated test suite (including health, status, crypto, codec, image stego, audio stego, video stego, profiler, allocator, multimodal engine, steganalysis features, dataset generation, training pipeline, and API routes):

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest -v
```

All **162 automated tests** pass with zero errors.
