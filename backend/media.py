import subprocess
import uuid
from pathlib import Path
import gdown
from . import config


class MediaError(Exception):
    pass


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def save_bytes(data: bytes, ext: str) -> tuple[str, Path]:
    """Save raw bytes as an audio file under storage/audio and return (id, path)."""
    audio_id = new_id()
    path = config.AUDIO_DIR / f"{audio_id}{ext}"
    path.write_bytes(data)
    return audio_id, path


def extract_audio_from_video(video_bytes: bytes, ext: str) -> tuple[str, Path]:
    """Save an uploaded video temporarily, extract its audio track with ffmpeg as mp3."""
    audio_id = new_id()
    video_path = config.AUDIO_DIR / f"{audio_id}_source{ext}"
    audio_path = config.AUDIO_DIR / f"{audio_id}.mp3"
    video_path.write_bytes(video_bytes)

    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-acodec", "libmp3lame", "-q:a", "2",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    video_path.unlink(missing_ok=True)

    if result.returncode != 0 or not audio_path.exists():
        raise MediaError(f"فشل استخراج الصوت من الفيديو: {result.stderr[-500:]}")

    return audio_id, audio_path


def import_from_drive(url: str, audio_id: str | None = None) -> tuple[str, Path]:
    """Download a single audio file shared via a Google Drive link."""
    audio_id = audio_id or new_id()
    try:
        # trailing slash -> gdown infers the real filename/extension from Drive metadata
        downloaded = gdown.download(url=url, output=str(config.AUDIO_DIR) + "/", fuzzy=True, quiet=True)
    except Exception as e:
        raise MediaError(f"تعذّر تنزيل الملف من Google Drive: {e}")

    if not downloaded:
        raise MediaError("تعذّر تنزيل الملف من Google Drive — تأكد من أن الرابط عام (Anyone with the link).")

    src = Path(downloaded)
    ext = src.suffix if src.suffix else ".mp3"
    final_path = config.AUDIO_DIR / f"{audio_id}{ext}"
    src.rename(final_path)
    return audio_id, final_path
