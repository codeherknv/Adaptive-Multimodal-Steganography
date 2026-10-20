# System Architecture

## Overview
This platform implements **Reliability-Aware Adaptive Multimodal Steganography with Machine-Learning-Based Steganalysis Across Image, Audio and Video**.

The system decouples the user-facing web interface from a Python-based research and evaluation engine.

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

## Security & Architectural Principles
1. **Separation of Concerns**: Cryptographic operations and steganographic embedding happen strictly on the backend. The frontend handles UX, input validation, and interactive visualization.
2. **Key Hygiene**: Secret keys are never stored inside media carriers or committed to Git. Authenticated decryption (AES-256-GCM) ensures any carrier corruption or tampering is detected prior to plaintext release.
3. **Chunk Framing**: Payloads are serialized with explicit version, message ID, chunk index, total chunk count, and CRC/length metadata to detect partial or reordered carrier sets.
4. **Transparent Degradation**: If an audio or video carrier is corrupted or missing, the receiver reports cryptographic authentication failure without crashing or returning garbage.
