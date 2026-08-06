# صدى (Sada) — من الصوت إلى التقرير

تطبيق ويب بسيط يحوّل تسجيلًا صوتيًا (تسجيل مباشر، ملف مرفوع، فيديو، أو رابط Google Drive)
إلى نص مفرَّغ ثم إلى تقرير عربي منظم عبر LangChain وواجهة ChatGPT البرمجية.

## المكوّنات

- **الواجهة الأمامية**: HTML/CSS/JS بسيطة بدون أدوات بناء، بتصميم RTL بخط Cairo.
- **الخلفية**: FastAPI (Python) تُقدّم الواجهة وتُنفّذ خط الأنابيب:
  1. استقبال الصوت (تسجيل / رفع / استخراج من فيديو عبر ffmpeg / استيراد من Drive عبر gdown)
  2. تفريغ النص عبر واجهة OpenAI الصوتية (Whisper)
  3. تلخيص وهيكلة النص في تقرير عربي عبر LangChain + ChatGPT

## طريقتا التشغيل

### 1) الكل في مكان واحد — GitHub Codespaces (الأسهل)
الواجهة والخادم يعملان معًا على نفس الرابط، والتفريغ الصوتي عبر Whisper API من OpenAI.

### 2) مُقسَّم — واجهة على GitHub Pages + خادم على Kaggle (GPU مجاني)
الواجهة تُستضاف كصفحة ثابتة على GitHub Pages، بينما الخادم يعمل داخل Kaggle Notebook مستفيدًا من
الـ GPU المجاني لتشغيل نموذج التفريغ العربي المحلي (`CohereLabs/cohere-transcribe-arabic-07-2026`
— نفس نموذج الدفتر الأصلي) بدل الدفع لـ Whisper API، ثم يُفتح رابط عام عبر Cloudflare Tunnel
(وضع Quick Tunnel — بدون تسجيل حساب أو توكن).

**فروقات مهمة عن الوضع الأول — اقرأها قبل الاعتماد على هذا الوضع:**
- Kaggle Notebooks لا تفتح منافذ واردة بشكل دائم؛ الرابط العام (Cloudflare Tunnel) **يتغيّر في كل
  جلسة جديدة** ولازم تلصقه يدويًا في زر "رابط الخادم" أعلى الواجهة كل مرة.
- الخادم يفضل شغّال بس طول ما جلسة Kaggle مفتوحة — مش استضافة دائمة، وأقرب لعرض تجريبي/استخدام شخصي متقطع.
- النموذج `CohereLabs/cohere-transcribe-arabic-07-2026` **مقيّد (gated)** على Hugging Face — لازم
  تطلب الوصول إليه من صفحته أولًا (Request access) وتستخدم توكن بصلاحية قراءة، وإلا هتاخد خطأ 403.
- تفعيل هذا الوضع يعني تركيب مكتبات ثقيلة (torch/transformers) — بيحصل جوه Kaggle فقط، مش على Codespace.

---

## التشغيل على GitHub Codespaces (الوضع الأول)

1. أنشئ Codespace من هذا المستودع (Code → Codespaces → Create codespace).
2. أضف مفتاح OpenAI كسرّ في الكودسبيس **قبل** إنشائه أو من خلاله لاحقًا:
   `Settings → Secrets and variables → Codespaces → New secret`
   الاسم: `OPENAI_API_KEY`
   *(يمكن أيضًا إضافة `CHAT_MODEL`, `STT_MODEL`, `MONTHLY_TOKEN_BUDGET` بنفس الطريقة، وإلا تُستخدم القيم الافتراضية في `.env.example`)*
3. عند فتح الكودسبيس، سيقوم `postCreateCommand` تلقائيًا بتثبيت `ffmpeg` واعتماديات Python.
4. شغّل الخادم:
   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```
5. سيقترح Codespaces فتح المنفذ 8000 في المتصفح تلقائيًا — أو من تبويب **PORTS**.

## التشغيل محليًا

```bash
cp .env.example .env      # ثم ضع مفتاح OPENAI_API_KEY فيه
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

افتح `http://localhost:8000`.

## التشغيل المُقسَّم — الوضع الثاني

### أ) نشر الواجهة على GitHub Pages
1. ارفع المستودع على GitHub (هيكون فيه ملف الووركفلو `.github/workflows/deploy-pages.yml` جاهز).
2. من إعدادات المستودع: **Settings → Pages → Source → GitHub Actions**.
3. أي push على `main` يعدّل مجلد `frontend/` يشغّل النشر تلقائيًا. الصفحة هتبقى متاحة على
   `https://<username>.github.io/<repo>/`.

### ب) تشغيل الخادم على Kaggle
1. ارفع دفتر `kaggle/sada_ai_kaggle_backend.ipynb` على Kaggle (New Notebook → Import Notebook).
2. فعّل GPU وInternet من Settings، وأضف الأسرار المطلوبة (`OPENAI_API_KEY`, `HF_TOKEN`) من
   Add-ons → Secrets — التفاصيل داخل الدفتر نفسه. (Cloudflare Quick Tunnel لا يحتاج أي سرّ إضافي —
   بدون حساب أو توكن، على عكس ngrok سابقًا.)
3. عدّل `REPO_URL` في الخلية الثانية لرابط مستودعك، ثم **Run All**.
4. آخر خلية هتطبع رابط Cloudflare Tunnel العام (`https://xxxx.trycloudflare.com`) — انسخه.

### ج) الربط بين الاثنين
افتح رابط GitHub Pages، اضغط زر **"رابط الخادم"** أعلى الصفحة، الصق رابط Cloudflare Tunnel، واضغط
"حفظ واختبار الاتصال". النقطة بجانب الزر بتتحول لأخضر لو الاتصال ناجح.

بديل بدون خطوة يدوية: لو عندك نفق Cloudflare دائم (Named Tunnel) برابط ثابت، أو أي رابط خادم ثابت
آخر، يمكنك ضبطه مرة واحدة في `frontend/config.js` (المتغيّر `API_BASE_URL`) بدل استخدام الزر في كل مرة.

## ملاحظة مهمة بخصوص "الرصيد المتبقي من الرموز"

واجهة OpenAI البرمجية العادية (مفتاح API قياسي) **لا تكشف عن رصيد الحساب الفعلي** —
هذه البيانات متاحة فقط عبر مفتاح إداري على مستوى المؤسسة (Org Admin Key)، وهو غير مناسب
لتطبيق مستخدم عادي. لذلك، الحلقة الظاهرة في أعلى الصفحة تعقب **استهلاكًا محليًا** لرموز
خطوة التلخيص فقط (LangChain/ChatGPT)، مقابل ميزانية شهرية تحددها أنت عبر `MONTHLY_TOKEN_BUDGET`.
البيانات تُخزَّن في `backend/storage/usage.json` وتُصفَّر تلقائيًا كل شهر. هذا ينطبق في كلا وضعي
التشغيل — خطوة التفريغ الصوتي نفسها (سواء Whisper API أو النموذج المحلي على Kaggle) لا تُحتسب
بالرموز أصلًا (تُحتسب بالدقيقة عند OpenAI، ومجانية على GPU Kaggle).

## اختيار خطوة التفريغ الصوتي (STT_PROVIDER)

| القيمة | الوصف | أين تعمل |
|---|---|---|
| `openai` (افتراضي) | Whisper API من OpenAI — بسيطة وسريعة الإعداد | Codespaces أو أي مكان |
| `local` | نموذج `CohereLabs/cohere-transcribe-arabic-07-2026` المحلي، بنفس معالجة الدفتر الأصلي (تحسين الصوت عبر ffmpeg ثم تقسيم لمقاطع 60 ثانية ثم استدلال دفعي) | يحتاج GPU — مُعَدّ للعمل داخل دفتر Kaggle المرفق |

## قيود معروفة (لإبقاء الكود بسيطًا)

- حد حجم الملف الصوتي المُرسَل لواجهة Whisper هو 25MB (حد OpenAI نفسه) — الملفات الأكبر
  تحتاج إلى تقسيم يدوي قبل الرفع؛ لم يُضَف تقسيم تلقائي حفاظًا على بساطة الكود.
- تخزين المهام (`jobs.json`) وملف الاستخدام محليان على القرص — مناسبان للاستخدام
  الفردي على Codespace، وليسا مصممين لتزامن عدة مستخدمين في آن واحد.
- رابط Google Drive يجب أن يشير إلى **ملف واحد عام** (Anyone with the link)، وليس مجلدًا.

## هيكل المشروع

```
sada-ai/
├── .devcontainer/devcontainer.json   # إعداد GitHub Codespaces
├── .github/workflows/deploy-pages.yml # نشر frontend/ تلقائيًا على GitHub Pages
├── kaggle/sada_ai_kaggle_backend.ipynb # يشغّل الخادم + النموذج المحلي + نفق Cloudflare على Kaggle
├── backend/
│   ├── main.py               # تطبيق FastAPI ونقاط النهاية (+ CORS)
│   ├── config.py               # الإعدادات من متغيرات البيئة
│   ├── stt.py                   # موزّع بين OpenAI Whisper والنموذج المحلي (STT_PROVIDER)
│   ├── stt_openai.py             # تفريغ عبر Whisper API
│   ├── stt_local.py               # تفريغ محلي (Cohere Arabic) — لتشغيله على Kaggle فقط
│   ├── stt_errors.py               # نوع الخطأ المشترك بين الاثنين
│   ├── summarizer.py                # سلسلة LangChain لإنشاء التقرير
│   ├── media.py                      # استخراج صوت من فيديو + استيراد من Drive
│   ├── token_tracker.py               # تعقّب استهلاك الرموز الشهري
│   ├── jobs.py                         # تخزين بيانات كل ملف صوتي
│   ├── requirements.txt                # اعتماديات أساسية (خفيفة، تكفي Codespaces)
│   ├── requirements-kaggle.txt          # اعتماديات إضافية للنموذج المحلي (torch/transformers)
│   └── storage/                          # الملفات الصوتية والنصوص والتقارير (غير مرفوعة لـ git)
├── frontend/
│   ├── index.html      # نفس الملفات تعمل في وضعي التشغيل (مسارات نسبية)
│   ├── style.css
│   ├── config.js          # متغيّر واحد API_BASE_URL لضبط رابط الخادم الافتراضي (اختياري)
│   └── app.js               # فيه إدارة "رابط الخادم" لوضع الاستضافة المُقسَّم
└── .env.example
```
