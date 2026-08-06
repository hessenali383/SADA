"""Dispatches to the OpenAI Whisper API or the local Kaggle-GPU model, per STT_PROVIDER.
The unused implementation is never imported, so a Codespace running the "openai" provider
never needs torch/transformers installed.
"""
from pathlib import Path
from . import config
from .stt_errors import TranscribeError

__all__ = ["transcribe", "TranscribeError", "preload"]


def transcribe(audio_path: Path) -> str:
    if config.STT_PROVIDER == "local":
        from . import stt_local
        return stt_local.transcribe(audio_path)
    from . import stt_openai
    return stt_openai.transcribe(audio_path)


def preload() -> None:
    """Optional warm-up hook, only meaningful for the local provider."""
    if config.STT_PROVIDER == "local":
        from . import stt_local
        stt_local.preload()
