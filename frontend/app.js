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

// ---------- Debug log panel ----------
// A visible, on-page console (bottom panel) that records every API call, its
// outcome, and any uncaught JS error — so problems (dead tunnel, expired
// server URL, stopped Kaggle session, ...) are visible without opening the
// browser DevTools.
const MAX_LOG_ROWS = 300;
let logCount = 0;
let logHasError = false;

function logEvent(level, title, detail) {
  logCount++;
  if (level === "error") logHasError = true;

  const consoleEl = el("logConsole");
  consoleEl.querySelector(".log-empty")?.remove();

  const time = new Date().toLocaleTimeString("ar-EG", { hour12: false });
  const row = document.createElement("div");
  row.className = `log-row ${level}`;

  const head = document.createElement("div");
  head.className = "log-row-head";
  const timeSpan = document.createElement("span");
  timeSpan.className = "log-row-time";
  timeSpan.textContent = time;
  const titleSpan = document.createElement("span");
  titleSpan.className = "log-row-title";
  titleSpan.textContent = title;
  head.append(timeSpan, titleSpan);
  row.appendChild(head);

  if (detail) {
    const d = document.createElement("div");
    d.className = "log-row-detail";
    d.textContent = detail;
    row.appendChild(d);
  }

  consoleEl.appendChild(row);
  while (consoleEl.children.length > MAX_LOG_ROWS) consoleEl.removeChild(consoleEl.firstChild);
  consoleEl.scrollTop = consoleEl.scrollHeight;

  el("logBarCount").textContent = String(logCount);
  el("logBarDot").classList.toggle("err", logHasError);

  (level === "error" ? console.error : console.log)(`[صدى] ${title}`, detail || "");
}

const logPanelEl = el("logPanel");
el("logBar").addEventListener("click", () => {
  const open = logPanelEl.classList.toggle("open");
  el("logBody").hidden = !open;
  el("logBar").setAttribute("aria-expanded", String(open));
  el("logBarArrow").textContent = open ? "▼" : "▲";
});
el("logClearBtn").addEventListener("click", (e) => {
  e.stopPropagation();
  el("logConsole").innerHTML = '<p class="log-empty">لا توجد أحداث بعد.</p>';
  logCount = 0;
  logHasError = false;
  el("logBarCount").textContent = "0";
  el("logBarDot").classList.remove("err");
});
el("logCopyBtn").addEventListener("click", async (e) => {
  e.stopPropagation();
  const lines = [...el("logConsole").querySelectorAll(".log-row")].map((r) => {
    const t = r.querySelector(".log-row-time")?.textContent || "";
    const title = r.querySelector(".log-row-title")?.textContent || "";
    const detail = r.querySelector(".log-row-detail")?.textContent || "";
    return detail ? `${t}  ${title}\n    ${detail.replace(/\n/g, "\n    ")}` : `${t}  ${title}`;
  });
  const btn = el("logCopyBtn");
  try {
    await navigator.clipboard.writeText(lines.join("\n"));
    btn.textContent = "تم النسخ ✓";
  } catch {
    btn.textContent = "تعذّر النسخ";
  }
  setTimeout(() => (btn.textContent = "نسخ"), 1200);
});

window.addEventListener("error", (e) => {
  logEvent("error", "خطأ غير متوقع في الواجهة", `${e.message}\n${e.filename || ""}:${e.lineno || ""}`);
});
window.addEventListener("unhandledrejection", (e) => {
  logEvent("error", "طلب لم تتم معالجته (Promise)", String(e.reason?.message || e.reason || ""));
});

// Safe fetch wrapper: logs every request/response, and never calls res.json()
// blindly. It reads the body as text first and only then tries to parse it,
// so a non-JSON response (e.g. an HTML error page returned when a Cloudflare
// Tunnel / Kaggle session has died) becomes a clear log entry instead of the
// opaque browser error "Unexpected token '<' ... is not valid JSON".
async function apiFetch(path, options = {}, { silent = false } = {}) {
  const url = apiUrl(path);
  const method = (options.method || "GET").toUpperCase();
  if (!silent) logEvent("info", `→ ${method} ${path}`);

  let res;
  try {
    res = await fetch(url, options);
  } catch (networkErr) {
    logEvent("error", `تعذّر الوصول إلى ${path}`, `${networkErr.message}\nالرابط المستخدم: ${url || "(فارغ — لم يُضبط رابط الخادم)"}`);
    throw new Error("تعذّر الاتصال بالخادم — تحقق من رابط الخادم ومن أن الجلسة (Codespace/Kaggle) ما زالت تعمل");
  }

  const raw = await res.text();
  let data = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    logEvent(
      "error",
      `استجابة غير صالحة من ${path} (HTTP ${res.status})`,
      `الرد ليس JSON — الأرجح أنها صفحة HTML من الخادم/النفق بدل رد التطبيق (يعني عادة أن جلسة Kaggle توقفت، أو أن Cloudflare أوقف الطلب لأنه استغرق أكثر من ~100 ثانية، أو أن رابط Cloudflare Tunnel انتهت صلاحيته).\nأول جزء من الرد:\n${raw.slice(0, 300) || "(فارغ)"}`
    );
    throw new Error("الخادم أرجع استجابة غير صالحة (HTML بدل JSON) — على الأرجح انقطع الطلب بسبب المهلة الزمنية لـ Cloudflare (~100 ثانية) أو توقفت الجلسة");
  }

  if (!res.ok) {
    logEvent("error", `${method} ${path} → HTTP ${res.status}`, data.detail || "");
  } else if (!silent) {
    logEvent("success", `${method} ${path} → HTTP ${res.status}`);
  }
  return { res, data };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const POLL_INTERVAL_MS = 4000;
const PENDING_STATUSES = new Set(["importing", "transcribing", "summarizing"]);

// Repeatedly polls a status endpoint until the job leaves a "pending" state,
// instead of waiting on one long-lived HTTP response. This is required
// because Cloudflare's edge (including the free trycloudflare.com Quick
// Tunnels used here) cuts off any single request the backend hasn't fully
// answered within roughly 100-120 seconds and returns its own HTML error page
// — so a transcription or summary that takes minutes must be started, then
// checked periodically, rather than awaited in one call.
async function pollJob(statusPath, onTick) {
  while (true) {
    const { res, data } = await apiFetch(statusPath, {}, { silent: true });
    if (!res.ok) throw new Error(data.detail || "فشل الطلب");
    if (!PENDING_STATUSES.has(data.status)) return data;
    if (onTick) onTick(data.status);
    await sleep(POLL_INTERVAL_MS);
  }
}

async function pingServer() {
  try {
    const { res } = await apiFetch("/api/status");
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
    const { res, data } = await apiFetch("/api/status");
    if (!res.ok) throw new Error(data.detail || "فشل التحميل");
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

function uploadWithProgress(path, formData, onProgress) {
  const url = apiUrl(path);
  logEvent("info", `→ POST ${path} (رفع ملف)`);
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      let data;
      try {
        data = JSON.parse(xhr.responseText || "{}");
      } catch {
        logEvent(
          "error",
          `استجابة غير صالحة من ${path} (HTTP ${xhr.status})`,
          `الرد ليس JSON — الأرجح أنها صفحة HTML من الخادم/النفق بدل رد التطبيق.\nأول جزء من الرد:\n${(xhr.responseText || "").slice(0, 300) || "(فارغ)"}`
        );
        reject(new Error("الخادم أرجع استجابة غير صالحة (HTML بدل JSON) — تأكد من أن الجلسة ما زالت تعمل"));
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        logEvent("success", `POST ${path} → HTTP ${xhr.status}`);
        resolve(data);
      } else {
        logEvent("error", `POST ${path} → HTTP ${xhr.status}`, data.detail || "");
        reject(new Error(data.detail || "فشل الرفع"));
      }
    };
    xhr.onerror = () => {
      logEvent("error", `تعذّر الوصول إلى ${path}`, `الرابط المستخدم: ${url || "(فارغ — لم يُضبط رابط الخادم)"}`);
      reject(new Error("تعذّر الاتصال بالخادم"));
    };
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
        const job = await uploadWithProgress("/api/audio/record", formData, () => {});
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
    const job = await uploadWithProgress("/api/audio/upload", formData, (p) =>
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
    const job = await uploadWithProgress("/api/video/extract", formData, (p) =>
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
  const startedAt = Date.now();
  try {
    const { res, data: start } = await apiFetch("/api/drive/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    if (!res.ok) throw new Error(start.detail || "فشل الاستيراد");

    const job = await pollJob(`/api/drive/import/status/${start.audio_id}`, () => {
      const secs = Math.floor((Date.now() - startedAt) / 1000);
      setIntakeProgress(100, `جارٍ الاستيراد من Google Drive… (${secs} ث — قد يستغرق دقائق للملفات الكبيرة)`);
    });

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

  const startedAt = Date.now();
  try {
    const { res, data: start } = await apiFetch("/api/transcribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audio_id: job.audio_id }),
    });
    if (!res.ok) throw new Error(start.detail || "فشل التفريغ الصوتي");

    const data = await pollJob(`/api/transcribe/status/${job.audio_id}`, () => {
      const secs = Math.floor((Date.now() - startedAt) / 1000);
      const mins = Math.floor(secs / 60);
      const label = mins > 0 ? `${mins} د ${secs % 60} ث` : `${secs} ث`;
      el("fileStageLabel").textContent = `جارٍ تفريغ النص الصوتي… (${label} — قد يستغرق دقائق طويلة للتسجيلات الطويلة)`;
    });

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
  const startedAt = Date.now();
  try {
    const { res, data: start } = await apiFetch("/api/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audio_id: audioId }),
    });
    if (!res.ok) throw new Error(start.detail || "فشل إنشاء التقرير");

    const data = await pollJob(`/api/summarize/status/${audioId}`, () => {
      const secs = Math.floor((Date.now() - startedAt) / 1000);
      btn.textContent = `جارٍ إنشاء التقرير… (${secs} ث)`;
    });

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
