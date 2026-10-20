# Literature Review & Theoretical Foundations

## Core Principles
1. **Spatial Domain Steganography (LSB)**:
   - Early spatial LSB replacement modifies the least significant bits of pixel values or audio samples.
   - Known vulnerability: Asymmetrical pair-of-values transition probabilities make naive LSB vulnerable to Chi-square analysis and Sample Pairs analysis (Fridrich et al., 2001).
   - Modern adaptive steganography (e.g., WOW, S-UNIWARD, HILL) assigns embedding distortion costs to complex, textured regions rather than flat regions.

2. **Multimodal Payload Allocation**:
   - Most literature studies single-medium embedding (image-only or audio-only).
   - Splitting payload across independent modalities (heterogeneous channels) allows distributing embedding risk across spatial, temporal, and acoustic domains.
   - However, reassembly requires synchronized chunking metadata and strict error handling.

3. **Steganalysis Baselines**:
   - First-order statistical features (sample distributions, histogram pair-of-values).
   - Higher-order spatial co-occurrence / Markov transition features.
   - Supervised classification (Random Forest, SVM, MLP) trained on cover and stego feature vectors.
