from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.callbacks.manager import get_openai_callback
from . import config, token_tracker

SYSTEM_PROMPT = """أنت مساعد متخصص في تحويل نصوص مفرَّغة من تسجيلات صوتية (اجتماعات، محاضرات، مكالمات عمل) \
إلى تقرير عربي منظم واحترافي. اكتب بلغة عربية فصحى واضحة ومباشرة، بدون حشو، وحافظ على أي مصطلحات \
تقنية أو إنجليزية كما وردت في النص الأصلي. أخرج التقرير بصيغة Markdown بالعناوين التالية بالضبط:

## ملخص تنفيذي
## النقاط الرئيسية
## القرارات والإجراءات المطلوبة
## ملاحظات إضافية

إن لم يتوفر محتوى لعنوان معين، اكتب تحته: "لا يوجد."."""

HUMAN_PROMPT = "النص المفرَّغ من التسجيل الصوتي:\n\n{transcript}"


class SummarizeError(Exception):
    pass


def summarize(transcript: str) -> str:
    if not config.GEMINI_API_KEY:
        raise SummarizeError(
            "GEMINI_API_KEY غير موجود — أضِفه في Kaggle Secrets أو ملف .env"
        )

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    prompt = f"""{SYSTEM_PROMPT}

{HUMAN_PROMPT.format(transcript=transcript)}
"""

    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
    )

    if not response.text:
        raise SummarizeError("Gemini لم يُرجع تقريرًا.")

    return response.text.strip()
