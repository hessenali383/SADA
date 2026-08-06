from pathlib import Path
from openai import OpenAI
from . import config
from .stt_errors import TranscribeError

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        if not config.OPENAI_API_KEY:
            raise TranscribeError("OPENAI_API_KEY غير موجود — أضِفه في Codespaces Secrets أو ملف .env")
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def transcribe(audio_path: Path) -> str:
    size_mb = audio_path.stat().st_size / (1024 * 1024)
    if size_mb > 25:
        raise TranscribeError(
            f"حجم الملف {size_mb:.1f}MB يتجاوز الحد المسموح به لواجهة OpenAI (25MB). "
            "قسّم الملف إلى مقاطع أقصر وحاول مجددًا."
        )
    with open(audio_path, "rb") as f:
        text = client().audio.transcriptions.create(
            model=config.STT_MODEL,
            file=f,
            language=config.TRANSCRIBE_LANGUAGE,
            response_format="text",
        )
    return str(text).strip()
