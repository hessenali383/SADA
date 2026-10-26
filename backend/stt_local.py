import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

from . import config
from .stt_errors import TranscribeError

_lock = threading.Lock()
_model = None
_processor = None
_device = "cuda:0" if torch.cuda.is_available() else "cpu"
_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

_FILTERS = {
    "light": "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11",
    "full": "highpass=f=80,lowpass=f=7600,afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11",
}


def _load_model() -> None:
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
                pass
        processor = AutoProcessor.from_pretrained(config.LOCAL_ASR_MODEL)
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            config.LOCAL_ASR_MODEL, dtype=_dtype, low_cpu_mem_usage=True, use_safetensors=True,
        ).to(_device)
        model.eval()
        _model, _processor = model, processor


def preload() -> None:
    try:
        _load_model()
    except Exception as e:
        print(f"[stt_local] تحذير: تعذّر تحميل النموذج المحلي مسبقًا: {e}")


def _prepare_audio(input_path: str, output_path: str) -> bool:
    cmd = ["ffmpeg", "-y", "-i", input_path, "-vn"]
    chain = _FILTERS.get(config.LOCAL_ASR_ENHANCE)
    if chain:
        cmd += ["-af", chain]
    cmd += ["-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0 and Path(output_path).exists()


def collapse_repeats(text: str, max_rep: int = 3, max_n: int = 8) -> str:
    """Safety net: collapse any word/phrase loop repeated more than max_rep times into one occurrence."""
    w = text.split()
    out, i = [], 0
    while i < len(w):
        hit = False
        for n in range(1, max_n + 1):
            seg = w[i:i + n]
            if len(seg) < n:
                break
            reps = 1
            while w[i + reps * n:i + (reps + 1) * n] == seg:
                reps += 1
            if reps > max_rep:
                out.extend(seg)
                i += reps * n
                hit = True
                break
        if not hit:
            out.append(w[i])
            i += 1
    return " ".join(out)


def _language():
    lang = (config.LOCAL_ASR_LANGUAGE or "").strip().lower()
    return None if lang in ("", "auto") else lang


@torch.inference_mode()
def _run(audio: np.ndarray) -> str:
    proc = _processor
    inputs = proc(audio, sampling_rate=16000, return_tensors="pt", truncation=False,
                  padding="longest", return_attention_mask=True)
    if inputs.input_features.shape[-1] < 3000:
        inputs = proc(audio, sampling_rate=16000, return_tensors="pt", return_attention_mask=True)

    kwargs = dict(
        input_features=inputs.input_features.to(_device, dtype=_dtype),
        task="transcribe",
        return_timestamps=True,
        condition_on_prev_tokens=False,
        compression_ratio_threshold=1.35,
        logprob_threshold=-1.0,
        no_speech_threshold=0.6,
        temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
        num_beams=config.LOCAL_ASR_NUM_BEAMS,
    )
    if inputs.get("attention_mask") is not None:
        kwargs["attention_mask"] = inputs.attention_mask.to(_device)
    lang = _language()
    if lang:
        kwargs["language"] = lang

    ids = _model.generate(**kwargs)
    return proc.batch_decode(ids, skip_special_tokens=True)[0].strip()


def transcribe(audio_path: Path) -> str:
    _load_model()
    work_dir = Path(tempfile.mkdtemp(prefix="asr_"))
    try:
        wav = work_dir / "clean.wav"
        if not _prepare_audio(str(audio_path), str(wav)):
            raise TranscribeError("فشلت معالجة الصوت الأولية عبر ffmpeg")
        audio = sf.read(str(wav), dtype="float32")[0]
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if audio.size == 0:
            raise TranscribeError("الملف الصوتي فارغ")
        try:
            text = _run(audio)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            raise TranscribeError("نفدت ذاكرة الـ GPU أثناء التفريغ")
        return collapse_repeats(text)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
