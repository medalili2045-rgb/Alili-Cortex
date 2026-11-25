# Media preprocessing

Vayron's local media preprocessing is implemented in `src/vayron_core/media_pipeline.py`.

- `process_image` verifies and decodes one local image at a time, applies EXIF orientation, enforces byte/pixel limits, resizes, and writes an RGB JPEG derivative with source SHA-256.
- `process_video` uses FFprobe/FFmpeg to inspect a local video and sample a bounded number of frames without loading the whole video into memory.
- Both functions reject paths escaping the configured asset root. They do not download assets, infer licenses, or perform semantic image/video understanding.
- Input manifests must still carry explicit source and license provenance and be reviewed before processing.
- Video processing requires FFmpeg and FFprobe on PATH. Image processing requires Pillow.

Install optional media dependencies with `pip install -e ".[media]"`. FFmpeg is a system executable and must be installed separately if absent.

The output derivatives are preprocessing artifacts only. A pretrained vision encoder, image-text alignment, temporal video encoder, multimodal training, and model-level visual evaluation remain future work.
