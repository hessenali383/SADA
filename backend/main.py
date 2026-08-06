from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
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


def _run_drive_import(audio_id: str, url: str):
    try:
        _, path = media.import_from_drive(url, audio_id=audio_id)
    except media.MediaError as e:
        jobs.update(audio_id, status="import_failed", error=str(e))
        return
    jobs.update(audio_id, status="uploaded", filename=path.name, path=str(path))


@app.post("/api/drive/import")
def drive_import(body: DriveImportRequest, background_tasks: BackgroundTasks):
    audio_id = media.new_id()
    jobs.create(audio_id, source="drive", status="importing")
    background_tasks.add_task(_run_drive_import, audio_id, body.url)
    return {"audio_id": audio_id, "status": "importing"}


@app.get("/api/drive/import/status/{audio_id}")
def drive_import_status(audio_id: str):
    job = jobs.get(audio_id)
    if not job:
        raise HTTPException(404, "غير موجود")
    if job.get("status") == "import_failed":
        raise HTTPException(400, job.get("error") or "فشل الاستيراد")
    if job.get("status") == "importing":
        return {"audio_id": audio_id, "status": "importing"}
    return _job_response(audio_id, job)


class AudioIdRequest(BaseModel):
    audio_id: str


# ---------------------------------------------------------------------------
# Transcription and summarization run as background jobs instead of blocking
# the request. Reason: Cloudflare's edge (including the free trycloudflare.com
# Quick Tunnels used for the split-hosting mode) drops any HTTP request that
# the origin hasn't fully answered within ~100-120 seconds, and returns its own
# HTML error page instead — which the frontend can't parse as JSON. A long
# recording easily takes longer than that to transcribe (or, on a big prompt,
# to summarize), so those endpoints must return immediately and let the client
# poll for the result instead of waiting on a single long-lived response.
# ---------------------------------------------------------------------------

def _run_transcription(audio_id: str, audio_path: str):
    try:
        text = stt.transcribe(Path(audio_path))
    except stt.TranscribeError as e:
        jobs.update(audio_id, status="transcribe_failed", error=str(e))
        return
    except Exception as e:
        jobs.update(audio_id, status="transcribe_failed", error=f"فشل التفريغ الصوتي: {e}")
        return
    txt_path = config.TRANSCRIPT_DIR / f"{audio_id}.txt"
    txt_path.write_text(text, encoding="utf-8")
    jobs.update(audio_id, status="transcribed", transcript_path=str(txt_path), word_count=len(text.split()))


@app.post("/api/transcribe")
def transcribe(body: AudioIdRequest, background_tasks: BackgroundTasks):
    job = jobs.get(body.audio_id)
    if not job:
        raise HTTPException(404, "الملف الصوتي غير موجود")

    jobs.update(body.audio_id, status="transcribing", error=None)
    background_tasks.add_task(_run_transcription, body.audio_id, job["path"])
    return {"audio_id": body.audio_id, "status": "transcribing"}


@app.get("/api/transcribe/status/{audio_id}")
def transcribe_status(audio_id: str):
    job = jobs.get(audio_id)
    if not job:
        raise HTTPException(404, "الملف الصوتي غير موجود")
    if job.get("status") == "transcribe_failed":
        raise HTTPException(400, job.get("error") or "فشل التفريغ الصوتي")
    if job.get("status") != "transcribed":
        return {"audio_id": audio_id, "status": job.get("status", "transcribing")}
    return {
        "audio_id": audio_id,
        "status": "transcribed",
        "transcript": Path(job["transcript_path"]).read_text(encoding="utf-8"),
        "word_count": job["word_count"],
    }


def _run_summarize(audio_id: str, transcript_path: str):
    transcript = Path(transcript_path).read_text(encoding="utf-8")
    try:
        report = summarizer.summarize(transcript)
    except summarizer.SummarizeError as e:
        jobs.update(audio_id, status="summarize_failed", error=str(e))
        return
    except Exception as e:
        jobs.update(audio_id, status="summarize_failed", error=f"فشل إنشاء التقرير: {e}")
        return
    report_path = config.REPORT_DIR / f"{audio_id}.txt"
    report_path.write_text(report, encoding="utf-8")
    jobs.update(audio_id, status="summarized", report_path=str(report_path))


@app.post("/api/summarize")
def summarize(body: AudioIdRequest, background_tasks: BackgroundTasks):
    job = jobs.get(body.audio_id)
    if not job or "transcript_path" not in job:
        raise HTTPException(404, "لا يوجد نص مفرَّغ لهذا الملف بعد")

    jobs.update(body.audio_id, status="summarizing", error=None)
    background_tasks.add_task(_run_summarize, body.audio_id, job["transcript_path"])
    return {"audio_id": body.audio_id, "status": "summarizing"}


@app.get("/api/summarize/status/{audio_id}")
def summarize_status(audio_id: str):
    job = jobs.get(audio_id)
    if not job:
        raise HTTPException(404, "غير موجود")
    if job.get("status") == "summarize_failed":
        raise HTTPException(400, job.get("error") or "فشل إنشاء التقرير")
    if job.get("status") != "summarized":
        return {"audio_id": audio_id, "status": job.get("status", "summarizing")}
    return {
        "audio_id": audio_id,
        "status": "summarized",
        "report": Path(job["report_path"]).read_text(encoding="utf-8"),
        "usage": token_tracker.status(),
    }


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
