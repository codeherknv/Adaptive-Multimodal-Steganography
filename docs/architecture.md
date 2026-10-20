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

## 4. Test Execution & Verification

To execute the complete automated test suite (including health, status, crypto, and codec tests):

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest -v
```

All 47 unit and integration tests pass with zero errors.
