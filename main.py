"""
bark-tts-server - FastAPI service for Bark TTS
Run: uvicorn main:app --host 0.0.0.0 --port 8000
"""
import os
import io
import time
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from scipy.io.wavfile import write as write_wav
import numpy as np

# ===================== إعدادات =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("bark-tts")

# تحميل متغيرات البيئة
from dotenv import load_dotenv
load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "500"))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
USE_SMALL_MODELS = os.getenv("USE_SMALL_MODELS", "false").lower() == "true"

# ===================== تحميل Bark (مرة واحدة عند بدء التشغيل) =====================
logger.info("⏳ جاري تحميل نماذج Bark... (قد يستغرق دقيقة أو أكثر)")
t0 = time.time()

try:
    from bark import SAMPLE_RATE, generate_audio, preload_models
    preload_models(
        text_use_small=USE_SMALL_MODELS,
        coarse_use_small=USE_SMALL_MODELS,
        fine_use_small=USE_SMALL_MODELS,
    )
    logger.info(f"✅ تم تحميل النماذج بنجاح خلال {time.time() - t0:.1f} ثانية")
    BARK_READY = True
except Exception as e:
    logger.error(f"❌ فشل تحميل Bark: {e}")
    BARK_READY = False

# ===================== FastAPI App =====================
app = FastAPI(
    title="Bark TTS Server",
    description="خدمة تحويل النص إلى كلام باستخدام Bark",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ThreadPool لأن Bark ثقيل ولا يعمل بشكل async
executor = ThreadPoolExecutor(max_workers=1)

# ===================== Models =====================
class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH,
                      description="النص المراد تحويله إلى كلام")
    voice_preset: Optional[str] = Field(
        default="v2/en_speaker_6",
        description="الصوت المستخدم (مثال: v2/en_speaker_0 حتى v2/en_speaker_9)"
    )
    history_prompt: Optional[str] = Field(default=None, description="موجه صوتي مخصص")


class TTSResponse(BaseModel):
    success: bool
    message: str
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None


# ===================== Endpoints =====================
@app.get("/")
async def root():
    return {
        "service": "Bark TTS",
        "status": "ready" if BARK_READY else "loading",
        "sample_rate": SAMPLE_RATE if BARK_READY else None,
    }


@app.get("/health")
async def health():
    if not BARK_READY:
        raise HTTPException(status_code=503, detail="Bark لم يتم تحميله بعد")
    return {"status": "ok", "sample_rate": SAMPLE_RATE}


def _generate_wav_bytes(text: str, voice_preset: str, history_prompt: Optional[str]) -> bytes:
    """توليد الصوت في thread منفصل (Bark ليس async)"""
    history = history_prompt if history_prompt else voice_preset
    audio_array = generate_audio(text, history_prompt=history)

    # تحويل إلى WAV في الذاكرة
    buffer = io.BytesIO()
    # Bark يرجع float32 في النطاق [-1, 1]، نحوله إلى int16
    if audio_array.dtype != np.int16:
        audio_int16 = (audio_array * 32767).astype(np.int16)
    else:
        audio_int16 = audio_array
    write_wav(buffer, SAMPLE_RATE, audio_int16)
    buffer.seek(0)
    return buffer.read()


@app.post("/synthesize", response_class=StreamingResponse)
async def synthesize(req: TTSRequest):
    """تحويل نص إلى ملف WAV"""
    if not BARK_READY:
        raise HTTPException(status_code=503, detail="Bark لم يتم تحميله بعد، حاول بعد قليل")

    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="النص فارغ")

    logger.info(f"🎙️ طلب جديد: {len(text)} حرف - preset: {req.voice_preset}")
    t0 = time.time()

    try:
        loop = asyncio.get_event_loop()
        wav_bytes = await loop.run_in_executor(
            executor, _generate_wav_bytes, text, req.voice_preset, req.history_prompt
        )
    except Exception as e:
        logger.exception("فشل توليد الصوت")
        raise HTTPException(status_code=500, detail=f"فشل توليد الصوت: {str(e)}")

    duration = time.time() - t0
    logger.info(f"✅ تم التوليد في {duration:.2f} ثانية")

    return StreamingResponse(
        io.BytesIO(wav_bytes),
        media_type="audio/wav",
        headers={
            "Content-Disposition": 'attachment; filename="bark_output.wav"',
            "X-Generation-Time": f"{duration:.2f}",
            "Cache-Control": "no-cache",
        },
    )


@app.post("/synthesize/json", response_model=TTSResponse)
async def synthesize_json(req: TTSRequest, background_tasks: BackgroundTasks):
    """نسخة JSON ترجع فقط معلومات، مفيدة للاختبار"""
    if not BARK_READY:
        raise HTTPException(status_code=503, detail="Bark لم يتم تحميله بعد")
    return TTSResponse(success=True, message="استخدم /synthesize للحصول على الملف الصوتي")


@app.get("/voices")
async def list_voices():
    """قائمة الأصوات المتاحة لـ Bark"""
    return {
        "voices": [f"v2/en_speaker_{i}" for i in range(10)],
        "note": "Bark يدعم حالياً الإنجليزية بشكل أساسي"
    }


# ===================== Startup / Shutdown =====================
@app.on_event("startup")
async def on_startup():
    logger.info(f"🚀 الخادم يعمل على http://{HOST}:{PORT}")
    if not BARK_READY:
        logger.warning("⚠️ Bark لم يتم تحميله، الخدمة سترجع 503")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("👋 إيقاف الخادم...")
    executor.shutdown(wait=False)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False, workers=1)
