from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import config, jobs, media, stt, summarizer, token_tracker

app = FastAPI(title="Sada AI")

# Works unchanged for any frontend origin, including a Cloudflare Tunnel-hosted backend
# (https://*.trycloudflare.com) called from a GitHub Pages frontend. No ngrok-style
# workaround header (e.g. "ngrok-skip-browser-warning") is required here: unlike ngrok's
# free tier, Cloudflare Quick Tunnels don't inject an interstitial browser-warning page
# in front of API responses, so allow_headers=["*"] below is already sufficient.
origins = ["*"] if config.ALLOWED_ORIGINS == "*" else [o.strip() for o in config.ALLOWED_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.on_event("startup")
def _warm_up():
    stt.preload()


@app.get("/api/status")
def status():
    return token_tracker.status()


def _ext_of(filename: str, fallback: str) -> str:
    ext = Path(filename or "").suffix.lower()
    return ext if ext else fallback


def _job_response(audio_id: str, job: dict) -> dict:
    return {"audio_id": audio_id, **job}


@app.post("/api/audio/upload")
async def upload_audio(file: UploadFile = File(...)):
    ext = _ext_of(file.filename, ".mp3")
    data = await file.read()
    audio_id, path = media.save_bytes(data, ext)
    job = jobs.create(audio_id, filename=file.filename, source="upload", status="uploaded", path=str(path))
    return _job_response(audio_id, job)


@app.post("/api/audio/record")
async def record_audio(file: UploadFile = File(...)):
    ext = _ext_of(file.filename, ".webm")
    data = await file.read()
    audio_id, path = media.save_bytes(data, ext)
    job = jobs.create(audio_id, filename="تسجيل مباشر" + ext, source="record", status="uploaded", path=str(path))
    return _job_response(audio_id, job)


@app.post("/api/video/extract")
async def extract_video(file: UploadFile = File(...)):
    ext = _ext_of(file.filename, ".mp4")
    data = await file.read()
    try:
        audio_id, path = media.extract_audio_from_video(data, ext)
    except media.MediaError as e:
        raise HTTPException(400, str(e))
    job = jobs.create(audio_id, filename=file.filename, source="video", status="uploaded", path=str(path))
    return _job_response(audio_id, job)


class DriveImportRequest(BaseModel):
    url: str


@app.post("/api/drive/import")
def drive_import(body: DriveImportRequest):
    try:
        audio_id, path = media.import_from_drive(body.url)
    except media.MediaError as e:
        raise HTTPException(400, str(e))
    job = jobs.create(audio_id, filename=path.name, source="drive", status="uploaded", path=str(path))
    return _job_response(audio_id, job)


class AudioIdRequest(BaseModel):
    audio_id: str


@app.post("/api/transcribe")
def transcribe(body: AudioIdRequest):
    job = jobs.get(body.audio_id)
    if not job:
        raise HTTPException(404, "الملف الصوتي غير موجود")

    try:
        text = stt.transcribe(Path(job["path"]))
    except stt.TranscribeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"فشل التفريغ الصوتي: {e}")

    txt_path = config.TRANSCRIPT_DIR / f"{body.audio_id}.txt"
    txt_path.write_text(text, encoding="utf-8")
    job = jobs.update(body.audio_id, status="transcribed", transcript_path=str(txt_path),
                       word_count=len(text.split()))
    return {"audio_id": body.audio_id, "transcript": text, "word_count": job["word_count"]}


@app.post("/api/summarize")
def summarize(body: AudioIdRequest):
    job = jobs.get(body.audio_id)
    if not job or "transcript_path" not in job:
        raise HTTPException(404, "لا يوجد نص مفرَّغ لهذا الملف بعد")

    transcript = Path(job["transcript_path"]).read_text(encoding="utf-8")
    try:
        report = summarizer.summarize(transcript)
    except summarizer.SummarizeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"فشل إنشاء التقرير: {e}")

    report_path = config.REPORT_DIR / f"{body.audio_id}.txt"
    report_path.write_text(report, encoding="utf-8")
    jobs.update(body.audio_id, status="summarized", report_path=str(report_path))
    return {"audio_id": body.audio_id, "report": report, "usage": token_tracker.status()}


@app.get("/api/download/transcript/{audio_id}")
def download_transcript(audio_id: str):
    job = jobs.get(audio_id)
    if not job or "transcript_path" not in job:
        raise HTTPException(404, "غير موجود")
    return FileResponse(job["transcript_path"], filename=f"transcript_{audio_id}.txt", media_type="text/plain")


@app.get("/api/download/report/{audio_id}")
def download_report(audio_id: str):
    job = jobs.get(audio_id)
    if not job or "report_path" not in job:
        raise HTTPException(404, "غير موجود")
    return FileResponse(job["report_path"], filename=f"report_{audio_id}.txt", media_type="text/plain")


# Mounted last (after every /api/* route above) so it only ever catches the frontend
# assets and "/" — with html=True it serves frontend/index.html for the root path.
# Kept as relative paths (style.css, app.js — not /static/style.css) so the exact
# same frontend files also work unmodified when served from GitHub Pages.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
