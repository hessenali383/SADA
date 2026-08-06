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

_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", HUMAN_PROMPT),
])


class SummarizeError(Exception):
    pass


def summarize(transcript: str) -> str:
    if not config.OPENAI_API_KEY:
        raise SummarizeError("OPENAI_API_KEY غير موجود — أضِفه في Codespaces Secrets أو ملف .env")

    llm = ChatOpenAI(model=config.CHAT_MODEL, api_key=config.OPENAI_API_KEY, temperature=0.2)
    chain = _prompt | llm

    with get_openai_callback() as cb:
        result = chain.invoke({"transcript": transcript})
        token_tracker.add_tokens(cb.total_tokens)

    return result.content.strip()
