import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import torch
import soundfile as sf
from transformers import AutoProcessor, CohereAsrForConditionalGeneration

from . import config
from .stt_errors import TranscribeError

_lock = threading.Lock()
_model = None
_processor = None


def _load_model() -> None:
    """Load the Cohere Arabic ASR model once and keep it resident for reuse across requests."""
    global _model, _processor
    if _model is not None:
        return
    with _lock:
        if _model is not None:
            return
        if config.HF_TOKEN:
            try:
                from huggingface_hub import login
                login(token=config.HF_TOKEN)
            except Exception:
                pass  # fall through — from_pretrained will raise a clear error if access is missing

        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        processor = AutoProcessor.from_pretrained(config.LOCAL_ASR_MODEL)
        model = CohereAsrForConditionalGeneration.from_pretrained(
            config.LOCAL_ASR_MODEL, device_map="auto", dtype=dtype,
        )
        model.eval()
        _model, _processor = model, processor


def preload() -> None:
    """Called at app startup so the first real request isn't stuck waiting for the model load."""
    try:
        _load_model()
    except Exception as e:
        print(f"[stt_local] تحذير: تعذّر تحميل النموذج المحلي مسبقًا: {e}")


def _enhance_audio(input_path: str, output_path: str) -> bool:
    """Denoise, normalize loudness, and resample to 16kHz mono — same filter chain as the notebook."""
    filter_chain = "highpass=f=80,lowpass=f=7600,afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11"
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af", filter_chain,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0 and Path(output_path).exists()


def _split_into_segments(input_path: str, out_dir: Path) -> list[str]:
    """Cut the cleaned WAV into fixed-length pieces via ffmpeg's segment muxer (same as the notebook)."""
    pattern = str(out_dir / "seg_%04d.wav")
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-f", "segment", "-segment_time", str(config.LOCAL_ASR_SEGMENT_SECONDS),
        "-reset_timestamps", "1",
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return sorted(str(p) for p in out_dir.glob("seg_*.wav"))


@torch.inference_mode()
def _transcribe_batch(seg_paths: list[str]) -> list[str]:
    audios = [sf.read(p, dtype="float32")[0] for p in seg_paths]
    inputs = _processor(audios, sampling_rate=16000, return_tensors="pt", language=config.TRANSCRIBE_LANGUAGE)
    audio_chunk_index = inputs.get("audio_chunk_index")
    inputs = inputs.to(_model.device, dtype=_model.dtype)
    outputs = _model.generate(**inputs, max_new_tokens=config.LOCAL_ASR_MAX_NEW_TOKENS)
    texts = _processor.decode(
        outputs, skip_special_tokens=True, audio_chunk_index=audio_chunk_index, language=config.TRANSCRIBE_LANGUAGE,
    )
    return [t.strip() for t in texts]


def transcribe(audio_path: Path) -> str:
    _load_model()
    work_dir = Path(tempfile.mkdtemp(prefix="asr_"))
    try:
        clean_path = work_dir / "clean.wav"
        if not _enhance_audio(str(audio_path), str(clean_path)):
            raise TranscribeError("فشلت معالجة الصوت الأولية عبر ffmpeg")

        seg_paths = _split_into_segments(str(clean_path), work_dir)
        if not seg_paths:
            raise TranscribeError("تعذّر تقسيم الملف الصوتي إلى مقاطع")

        texts: list[str] = []
        batch_size = config.LOCAL_ASR_BATCH_SIZE
        for i in range(0, len(seg_paths), batch_size):
            batch = seg_paths[i:i + batch_size]
            try:
                texts.extend(_transcribe_batch(batch))
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                for p in batch:
                    texts.extend(_transcribe_batch([p]))

        return " ".join(t for t in texts if t)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
