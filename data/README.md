# Data Directory

This directory stores datasets and media carriers used for research experiments:
- `cover/`: Unmodified carrier media (clean images, audio, video).
- `stego/`: Modified carrier media with embedded payloads.
- `splits/`: Train / validation / test partition lists to prevent data leakage.

> Note: Raw sample media and generated dataset artifacts should not be committed to Git. Small synthetic baseline samples can be generated programmatically for reproducible testing.
