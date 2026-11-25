import json
import pytest

from vayron_core.media_pipeline import MediaConfig, process_image, process_video


def test_image_processing_is_bounded_and_records_hash(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    source = tmp_path / "assets"
    source.mkdir()
    Image.new("RGB", (80, 40), "white").save(source / "sample.png")
    result = process_image(source, "sample.png", tmp_path / "out",
                           config=MediaConfig(max_image_side=32))
    assert result["width"] == 32
    assert result["height"] == 16
    assert len(result["source_sha256"]) == 64
    assert (tmp_path / result["processed_path"]).is_file()


def test_media_path_traversal_is_rejected(tmp_path):
    root = tmp_path / "assets"
    root.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"not-an-image")
    with pytest.raises(ValueError, match="escapes"):
        process_image(root, "../outside.jpg", tmp_path / "out")


def test_image_pixel_limit_is_enforced(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    source = tmp_path / "assets"
    source.mkdir()
    Image.new("RGB", (20, 20), "white").save(source / "large.png")
    with pytest.raises(ValueError, match="max_image_pixels"):
        process_image(source, "large.png", tmp_path / "out",
                      config=MediaConfig(max_image_pixels=100))


def test_video_requires_ffmpeg_tools_or_processes(tmp_path):
    import shutil
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg not installed")
    # An invalid file must fail safely rather than produce a fake frame manifest.
    source = tmp_path / "assets"
    source.mkdir()
    (source / "bad.mp4").write_bytes(b"not a video")
    with pytest.raises(Exception):
        process_video(source, "bad.mp4", tmp_path / "frames")
