"""
bark-tts-server - FastAPI service for Bark TTS (CPU ONLY)
Run: uvicorn main:app --host 0.0.0.0 --port 8000
"""
import os

# ============ فرض وضع CPU قبل أي import لـ torch ============
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"        # إخفاء أي GPU
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "0"  # تعطيل MPS (Mac GPU)
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# إعدادات Bark لتسريع CPU
os.environ.setdefault("SUNO_USE_SMALL_MODELS", "True")   # موديلات أصغر = أسرع
os.environ.setdefault("SUNO_OFFLOAD_CPU", "False")

import io
import time
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from scipy.io.wavfile import write as write_wav
import numpy as np

# ===================== إعدادات =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("bark-tts")

from dotenv import load_dotenv
load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "300"))  # أقل من قبل لأن CPU بطيء
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
USE_SMALL_MODELS = os.getenv("SUNO_USE_SMALL_MODELS", "True").lower() == "true"
CPU_THREADS = int(os.getenv("CPU_THREADS", str(os.cpu_count() or 4)))

# ===================== ضبط torch على CPU =====================
import torch
torch.set_num_threads(CPU_THREADS)
torch.set_num_interop_threads(max(1, CPU_THREADS // 2))

logger.info(f"🖥️  وضع CPU مُفعّل - {CPU_THREADS} threads")
logger.info(f"🚫 CUDA متاح؟ {torch.cuda.is_available()} (المتوقع: False)")

# ===================== تحميل Bark =====================
logger.info("⏳ جاري تحميل نماذج Bark على CPU... (قد يستغرق 3-10 دقائق)")
t0 = time.time()

try:
    from bark import SAMPLE_RATE, generate_audio, preload_models
    preload_models(
        text_use_small=USE_SMALL_MODELS,
        coarse_use_small=USE_SMALL_MODELS,
        fine_use_small=USE_SMALL_MODELS,
    )
    logger.info(f"✅ تم تحميل النماذج خلال {time.time() - t0:.1f} ثانية")
    logger.info(f"📦 استخدام موديلات صغيرة: {USE_SMALL_MODELS}")
    BARK_READY = True
except Exception as e:
    logger.error(f"❌ فشل تحميل Bark: {e}")
    BARK_READY = False

# ===================== FastAPI =====================
app = FastAPI(
    title="Bark TTS Server (CPU)",
    description="خدمة تحويل النص إلى كلام باستخدام Bark - تعمل على CPU بدون GPU",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# thread واحد فقط لأن Bark ثقيل على CPU
executor = ThreadPoolExecutor(max_workers=1)

# ===================== Models =====================
class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)
    voice_preset: Optional[str] = Field(default="v2/en_speaker_6")


# ===================== Endpoints =====================
@app.get("/")
async def root():
    return {
        "service": "Bark TTS (CPU only)",
        "status": "ready" if BARK_READY else "loading",
        "sample_rate": SAMPLE_RATE if BARK_READY else None,
        "device": "cpu",
        "threads": CPU_THREADS,
        "small_models": USE_SMALL_MODELS,
    }


@app.get("/health")
async def health():
    if not BARK_READY:
        raise HTTPException(status_code=503, detail="Bark لم يتم تحميله بعد")
    return {
        "status": "ok",
        "sample_rate": SAMPLE_RATE,
        "device": "cpu",
        "cuda_available": torch.cuda.is_available(),
    }


def _generate_wav_bytes(text: str, voice_preset: str) -> bytes:
    """توليد الصوت في thread منفصل (Bark ليس async)"""
    audio_array = generate_audio(text, history_prompt=voice_preset)

    buffer = io.BytesIO()
    if audio_array.dtype != np.int16:
        audio_int16 = (audio_array * 32767).astype(np.int16)
    else:
        audio_int16 = audio_array
    write_wav(buffer, SAMPLE_RATE, audio_int16)
    buffer.seek(0)
    return buffer.read()


@app.post("/synthesize", response_class=StreamingResponse)
async def synthesize(req: TTSRequest):
    if not BARK_READY:
        raise HTTPException(status_code=503, detail="Bark لم يتم تحميله بعد")

    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="النص فارغ")

    logger.info(f"🎙️ طلب جديد: {len(text)} حرف | preset: {req.voice_preset}")
    t0 = time.time()

    try:
        loop = asyncio.get_event_loop()
        wav_bytes = await loop.run_in_executor(
            executor, _generate_wav_bytes, text, req.voice_preset
        )
    except Exception as e:
        logger.exception("فشل توليد الصوت")
        raise HTTPException(status_code=500, detail=f"فشل التوليد: {str(e)}")

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


@app.get("/voices")
async def list_voices():
    return {
        "voices": [f"v2/en_speaker_{i}" for i in range(10)],
        "note": "Bark يدعم الإنجليزية فقط حالياً"
    }


# ===================== Startup / Shutdown =====================
@app.on_event("startup")
async def on_startup():
    logger.info(f"🚀 الخادم يعمل على http://{HOST}:{PORT}")
    logger.info(f"💻 الوضع: CPU فقط (عدد الأنوية: {CPU_THREADS})")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("👋 إيقاف الخادم...")
    executor.shutdown(wait=False)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False, workers=1)
