import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
AUDIO_DIR = STORAGE_DIR / "audio"
TRANSCRIPT_DIR = STORAGE_DIR / "transcripts"
REPORT_DIR = STORAGE_DIR / "reports"
JOBS_FILE = STORAGE_DIR / "jobs.json"
USAGE_FILE = STORAGE_DIR / "usage.json"

for d in (AUDIO_DIR, TRANSCRIPT_DIR, REPORT_DIR):
    d.mkdir(parents=True, exist_ok=True)


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

STT_PROVIDER = os.getenv("STT_PROVIDER", "openai")
STT_MODEL = os.getenv("STT_MODEL", "whisper-1")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")

MONTHLY_TOKEN_BUDGET = int(os.getenv("MONTHLY_TOKEN_BUDGET", "1000000"))
TRANSCRIBE_LANGUAGE = os.getenv("TRANSCRIBE_LANGUAGE", "ar")

# Only used when STT_PROVIDER=local (runs the notebook's Cohere Arabic model on a GPU host)
HF_TOKEN = os.getenv("HF_TOKEN", "")
LOCAL_ASR_MODEL = os.getenv("LOCAL_ASR_MODEL", "CohereLabs/cohere-transcribe-arabic-07-2026")
LOCAL_ASR_SEGMENT_SECONDS = int(os.getenv("LOCAL_ASR_SEGMENT_SECONDS", "60"))
LOCAL_ASR_BATCH_SIZE = int(os.getenv("LOCAL_ASR_BATCH_SIZE", "8"))
LOCAL_ASR_MAX_NEW_TOKENS = int(os.getenv("LOCAL_ASR_MAX_NEW_TOKENS", "440"))

# Comma-separated list of allowed frontend origins for CORS (e.g. your GitHub Pages URL).
# "*" (default) is fine for the all-in-one Codespace deployment where frontend + backend
# share an origin; set it explicitly when splitting frontend/backend across hosts.
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "200"))
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".webm", ".ogg", ".mp4", ".mpeg", ".mpga"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
