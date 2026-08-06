const RING_CIRCUMFERENCE = 326.7;
const MINI_RING_CIRCUMFERENCE = 163.4;

const el = (id) => document.getElementById(id);

// ---------- Backend base URL (split hosting: GitHub Pages frontend + remote backend) ----------
// Empty string = same-origin (the default all-in-one Codespaces deployment).
// Priority: a URL saved at runtime via the "server URL" modal (localStorage) wins over
// the single API_BASE_URL constant in config.js — the modal is what you use to paste a
// fresh Cloudflare Tunnel URL each time the Kaggle notebook is restarted, since those
// URLs aren't fixed. API_BASE_URL is only the default for everyone who hasn't set one.
const API_BASE_KEY = "sada_api_base";
const getApiBase = () => (localStorage.getItem(API_BASE_KEY) || API_BASE_URL || "").replace(/\/+$/, "");
const setApiBase = (url) => localStorage.setItem(API_BASE_KEY, url.trim().replace(/\/+$/, ""));
const apiUrl = (path) => getApiBase() + path;

function setServerDot(state) {
  const dot = el("serverDot");
  dot.classList.remove("ok", "err");
  if (state === "ok" || state === "err") dot.classList.add(state);
}

async function pingServer() {
  try {
    const res = await fetch(apiUrl("/api/status"));
    if (!res.ok) throw new Error();
    setServerDot("ok");
    return true;
  } catch {
    setServerDot("err");
    return false;
  }
}

el("serverBtn").addEventListener("click", () => {
  el("serverInput").value = getApiBase();
  el("serverModalStatus").textContent = "";
  el("serverModal").hidden = false;
});
el("serverCloseBtn").addEventListener("click", () => (el("serverModal").hidden = true));
el("serverSaveBtn").addEventListener("click", async () => {
  setApiBase(el("serverInput").value);
  el("serverModalStatus").textContent = "جارٍ اختبار الاتصال…";
  const ok = await pingServer();
  el("serverModalStatus").textContent = ok ? "تم الاتصال بنجاح ✓" : "تعذّر الاتصال — تحقق من الرابط";
  if (ok) {
    refreshTokenStatus();
    setTimeout(() => (el("serverModal").hidden = true), 700);
  }
});
pingServer();

// ---------- Token ring (header) ----------
async function refreshTokenStatus() {
  try {
    const res = await fetch(apiUrl("/api/status"));
    const data = await res.json();
    const offset = RING_CIRCUMFERENCE * (1 - data.percent_remaining / 100);
    el("tokenRingFill").style.strokeDashoffset = offset;
    el("tokenRingLabel").textContent = `${data.percent_remaining}%`;
    el("tokenSub").textContent =
      `${data.used.toLocaleString("ar")} / ${data.budget.toLocaleString("ar")} رمز هذا الشهر`;
  } catch {
    el("tokenSub").textContent = "تعذّر تحميل بيانات الرصيد";
  }
}
refreshTokenStatus();

// ---------- Method tiles ----------
const methods = ["record", "upload", "video", "drive"];
document.querySelectorAll(".method-tile").forEach((tile) => {
  tile.addEventListener("click", () => {
    const method = tile.dataset.method;
    document.querySelectorAll(".method-tile").forEach((t) => t.classList.remove("active"));
    tile.classList.add("active");
    methods.forEach((m) => (el(`panel-${m}`).hidden = m !== method));
  });
});

// ---------- Shared intake progress UI ----------
function setIntakeProgress(percent, statusText) {
  const bar = el("intakeProgress");
  bar.hidden = false;
  el("intakeProgressFill").style.width = `${percent}%`;
  el("intakeStatus").textContent = statusText || "";
}
function resetIntakeProgress() {
  el("intakeProgress").hidden = true;
  el("intakeProgressFill").style.width = "0%";
  el("intakeStatus").textContent = "";
}

function uploadWithProgress(url, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText));
      else reject(new Error(JSON.parse(xhr.responseText || "{}").detail || "فشل الرفع"));
    };
    xhr.onerror = () => reject(new Error("تعذّر الاتصال بالخادم"));
    xhr.send(formData);
  });
}

// ---------- Recording ----------
let mediaRecorder, mediaChunks = [], recordStart, recordTimerHandle, audioCtx, analyser, barsHandle;

function buildBars(container, count) {
  container.innerHTML = "";
  for (let i = 0; i < count; i++) {
    const s = document.createElement("span");
    s.style.height = "4px";
    container.appendChild(s);
  }
}
buildBars(el("recordBars"), 28);

function animateLiveBars() {
  const data = new Uint8Array(analyser.frequencyBinCount);
  const bars = el("recordBars").children;
  function tick() {
    analyser.getByteFrequencyData(data);
    const step = Math.floor(data.length / bars.length);
    for (let i = 0; i < bars.length; i++) {
      const v = data[i * step] || 0;
      bars[i].style.height = `${4 + (v / 255) * 28}px`;
    }
    barsHandle = requestAnimationFrame(tick);
  }
  tick();
}

el("recordBtn").addEventListener("click", async () => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioCtx = new AudioContext();
    const source = audioCtx.createMediaStreamSource(stream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 128;
    source.connect(analyser);
    animateLiveBars();

    mediaChunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (e) => mediaChunks.push(e.data);
    mediaRecorder.onstop = async () => {
      cancelAnimationFrame(barsHandle);
      clearInterval(recordTimerHandle);
      stream.getTracks().forEach((t) => t.stop());
      audioCtx.close();
      el("recordBtn").classList.remove("recording");
      el("recordHint").textContent = "جارٍ رفع التسجيل…";
      const blob = new Blob(mediaChunks, { type: "audio/webm" });
      const formData = new FormData();
      formData.append("file", blob, "recording.webm");
      try {
        const job = await uploadWithProgress(apiUrl("/api/audio/record"), formData, () => {});
        el("recordHint").textContent = "اضغط الزر لبدء التسجيل من الميكروفون";
        onAudioReady(job);
      } catch (e) {
        el("recordHint").textContent = e.message;
      }
    };
    mediaRecorder.start();
    el("recordBtn").classList.add("recording");
    el("recordHint").textContent = "جارٍ التسجيل… اضغط لإيقاف التسجيل";
    recordStart = Date.now();
    recordTimerHandle = setInterval(() => {
      const s = Math.floor((Date.now() - recordStart) / 1000);
      el("recordTimer").textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
    }, 250);
  } catch {
    el("recordHint").textContent = "تعذّر الوصول إلى الميكروفون — تحقق من أذونات المتصفح";
  }
});

// ---------- Upload ----------
el("uploadInput").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  setIntakeProgress(0, "جارٍ رفع الملف…");
  try {
    const job = await uploadWithProgress(apiUrl("/api/audio/upload"), formData, (p) =>
      setIntakeProgress(p, `جارٍ رفع الملف… ${p}%`)
    );
    resetIntakeProgress();
    onAudioReady(job);
  } catch (err) {
    setIntakeProgress(0, err.message);
  }
});

// ---------- Video ----------
el("videoInput").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  setIntakeProgress(0, "جارٍ رفع الفيديو…");
  try {
    const job = await uploadWithProgress(apiUrl("/api/video/extract"), formData, (p) =>
      setIntakeProgress(p, p < 100 ? `جارٍ رفع الفيديو… ${p}%` : "جارٍ استخراج الصوت…")
    );
    resetIntakeProgress();
    onAudioReady(job);
  } catch (err) {
    setIntakeProgress(0, err.message);
  }
});

// ---------- Drive ----------
el("driveBtn").addEventListener("click", async () => {
  const url = el("driveInput").value.trim();
  if (!url) return;
  el("driveBtn").disabled = true;
  setIntakeProgress(100, "جارٍ الاستيراد من Google Drive…");
  el("intakeProgressFill").style.width = "100%";
  try {
    const res = await fetch(apiUrl("/api/drive/import"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const job = await res.json();
    if (!res.ok) throw new Error(job.detail || "فشل الاستيراد");
    resetIntakeProgress();
    onAudioReady(job);
  } catch (err) {
    setIntakeProgress(100, err.message);
  } finally {
    el("driveBtn").disabled = false;
  }
});

// ---------- Pipeline: audio -> transcript -> report ----------
const sourceLabels = { upload: "ملف مرفوع", record: "تسجيل مباشر", video: "مستخرج من فيديو", drive: "مستورد من Drive" };

function setStageRing(mode) {
  const fill = el("fileStageRingFill");
  fill.classList.toggle("indeterminate", mode === "spin");
  if (mode === "spin") {
    fill.style.strokeDashoffset = MINI_RING_CIRCUMFERENCE * 0.75;
  } else if (mode === "done") {
    fill.style.strokeDashoffset = 0;
  } else {
    fill.style.strokeDashoffset = MINI_RING_CIRCUMFERENCE;
  }
}

async function onAudioReady(job) {
  el("fileCard").hidden = false;
  el("fileName").textContent = job.filename || "ملف صوتي";
  el("fileSourceLabel").textContent = sourceLabels[job.source] || "";
  buildBars(el("fileBars"), 40);
  el("fileBars").querySelectorAll("span").forEach((s) => (s.style.height = `${4 + Math.random() * 26}px`));
  el("fileStageLabel").textContent = "جارٍ تفريغ النص الصوتي…";
  setStageRing("spin");
  el("transcriptCard").hidden = true;
  el("reportCard").hidden = true;
  el("fileCard").scrollIntoView({ behavior: "smooth", block: "center" });

  try {
    const res = await fetch(apiUrl("/api/transcribe"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audio_id: job.audio_id }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "فشل التفريغ الصوتي");
    setStageRing("done");
    el("fileStageLabel").textContent = "اكتمل تفريغ النص";
    showTranscript(job.audio_id, data.transcript, data.word_count);
  } catch (err) {
    setStageRing("idle");
    el("fileStageLabel").textContent = err.message;
  }
}

function showTranscript(audioId, text, wordCount) {
  el("transcriptCard").hidden = false;
  el("transcriptText").textContent = text || "لا يوجد نص.";
  el("wordCount").textContent = `${wordCount.toLocaleString("ar")} كلمة`;
  el("downloadTranscriptBtn").onclick = () => window.open(apiUrl(`/api/download/transcript/${audioId}`), "_blank");
  el("summarizeBtn").onclick = () => runSummarize(audioId);
  el("transcriptCard").scrollIntoView({ behavior: "smooth", block: "center" });
}

async function runSummarize(audioId) {
  const btn = el("summarizeBtn");
  btn.disabled = true;
  btn.textContent = "جارٍ إنشاء التقرير…";
  try {
    const res = await fetch(apiUrl("/api/summarize"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audio_id: audioId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "فشل إنشاء التقرير");
    el("reportCard").hidden = false;
    el("reportText").textContent = data.report;
    el("downloadReportBtn").onclick = () => window.open(apiUrl(`/api/download/report/${audioId}`), "_blank");
    el("reportCard").scrollIntoView({ behavior: "smooth", block: "center" });
    refreshTokenStatus();
  } catch (err) {
    alert(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "إنشاء تقرير ذكي ←";
  }
}
