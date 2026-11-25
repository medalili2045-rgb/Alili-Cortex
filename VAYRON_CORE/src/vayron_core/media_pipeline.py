"""Safe, bounded-memory local image/video preprocessing for Vayron.

This module never downloads assets. It requires callers to supply local files
whose provenance and license have already been reviewed. Pillow and FFmpeg are
optional runtime dependencies; media is processed one asset/frame at a time.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MediaConfig:
    max_asset_bytes: int = 512 * 1024 * 1024
    max_image_pixels: int = 40_000_000
    max_image_side: int = 1536
    video_sample_seconds: float = 2.0
    video_max_frames: int = 64
    ffmpeg_timeout_seconds: int = 180

    def validate(self) -> None:
        if self.max_asset_bytes < 1 or self.max_image_pixels < 1:
            raise ValueError("asset and pixel limits must be positive")
        if self.max_image_side < 1 or self.video_max_frames < 1:
            raise ValueError("image side and frame limits must be positive")
        if self.video_sample_seconds <= 0 or self.ffmpeg_timeout_seconds < 1:
            raise ValueError("sampling interval and timeout must be positive")


def _safe_asset(root: Path, relative_path: str, max_bytes: int) -> Path:
    base = root.resolve()
    candidate = (base / relative_path).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError("asset_path escapes media root")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    size = candidate.stat().st_size
    if size <= 0 or size > max_bytes:
        raise ValueError(f"asset size outside allowed range: {size}")
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def process_image(
    asset_root: str | Path,
    asset_path: str,
    output_dir: str | Path,
    *,
    config: MediaConfig | None = None,
) -> dict[str, Any]:
    """Verify and create a bounded RGB JPEG derivative for one image."""
    config = config or MediaConfig()
    config.validate()
    source = _safe_asset(Path(asset_root), asset_path, config.max_asset_bytes)
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("Image processing requires Pillow; install the 'media' extra") from exc

    Image.MAX_IMAGE_PIXELS = config.max_image_pixels
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(source) as image:
            image.verify()
        with Image.open(source) as image:
            if image.width * image.height > config.max_image_pixels:
                raise ValueError("image exceeds max_image_pixels")
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((config.max_image_side, config.max_image_side), Image.Resampling.LANCZOS)
            target = output / f"{source.stem}-{_sha256(source)[:12]}.jpg"
            image.save(target, format="JPEG", quality=90, optimize=True)
            width, height = image.size
    except Image.DecompressionBombError as exc:
        raise ValueError("image exceeds max_image_pixels") from exc
    except Image.DecompressionBombWarning as exc:
        raise ValueError("image exceeds max_image_pixels") from exc
    except Exception as exc:
        if isinstance(exc, (ValueError, RuntimeError)):
            raise
        raise ValueError(f"invalid or unsupported image: {source.name}") from exc
    return {
        "source_path": asset_path,
        "processed_path": str(target),
        "source_sha256": _sha256(source),
        "width": width,
        "height": height,
        "format": "JPEG",
    }


def process_video(
    asset_root: str | Path,
    asset_path: str,
    output_dir: str | Path,
    *,
    config: MediaConfig | None = None,
) -> dict[str, Any]:
    """Sample video frames with FFmpeg without loading the full video in RAM."""
    config = config or MediaConfig()
    config.validate()
    source = _safe_asset(Path(asset_root), asset_path, config.max_asset_bytes)
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("Video processing requires ffmpeg and ffprobe executables")

    probe = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,duration", "-of", "json", str(source)],
        check=True, capture_output=True, text=True, timeout=config.ffmpeg_timeout_seconds,
    )
    try:
        streams = json.loads(probe.stdout).get("streams", [])
        if not streams:
            raise ValueError("video has no video stream")
        stream = streams[0]
        width, height = int(stream["width"]), int(stream["height"])
        duration = float(stream.get("duration") or 0)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("could not read valid video metadata") from exc
    if width < 1 or height < 1 or width * height > config.max_image_pixels:
        raise ValueError("video frame dimensions exceed configured limit")
    if duration <= 0:
        raise ValueError("video duration is missing or invalid")

    frame_count = min(config.video_max_frames, max(1, int(duration / config.video_sample_seconds) + 1))
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    prefix = source.stem + "-" + _sha256(source)[:12]
    pattern = output / (prefix + "-%04d.jpg")
    fps = f"1/{config.video_sample_seconds:g}"
    subprocess.run(
        [ffmpeg, "-nostdin", "-v", "error", "-i", str(source),
         "-vf", f"fps={fps},scale='min({config.max_image_side},iw)':-2",
         "-frames:v", str(frame_count), "-q:v", "3", str(pattern)],
        check=True, capture_output=True, timeout=config.ffmpeg_timeout_seconds,
    )
    frames = sorted(output.glob(prefix + "-*.jpg"))
    if not frames:
        raise ValueError("FFmpeg produced no frames")
    return {
        "source_path": asset_path,
        "source_sha256": _sha256(source),
        "width": width,
        "height": height,
        "duration_seconds": duration,
        "sample_interval_seconds": config.video_sample_seconds,
        "frames": [
            {"path": str(frame), "sha256": _sha256(frame), "index": index}
            for index, frame in enumerate(frames)
        ],
    }
