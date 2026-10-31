from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import logging
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"
DEFAULT_ORIGIN = "https://hellenicdev.eu"
REQUEST_TIMEOUT_SECONDS = 30

log = logging.getLogger("uvicorn.error")


def allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", DEFAULT_ORIGIN)
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or [DEFAULT_ORIGIN]


def client_address(request: Request) -> str:
    """Rate-limit key.

    Render puts Cloudflare in front of the service, and Cloudflare overwrites
    CF-Connecting-IP with the visitor address. The socket peer is the fallback
    so a client-supplied X-Forwarded-For cannot mint a fresh limit bucket.
    """
    cloudflare_ip = (request.headers.get("cf-connecting-ip") or "").strip()
    if cloudflare_ip:
        return cloudflare_ip
    return get_remote_address(request)


RATE_LIMIT = os.getenv("RATE_LIMIT", "10/minute")

limiter = Limiter(key_func=client_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Browser clients are limited to the configured origins (default: the public site).
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

class Message(BaseModel):
    message: str

@app.post("/api/chat")
@limiter.limit(RATE_LIMIT)
def chat(request: Request, msg: Message):
    if not HF_TOKEN:
        raise HTTPException(status_code=503, detail="The assistant is not configured.")

    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }
    json_data = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": msg.message}]
    }
    try:
        response = requests.post(
            url, headers=headers, json=json_data, timeout=REQUEST_TIMEOUT_SECONDS
        )
    except requests.Timeout:
        log.warning("Hugging Face chat timed out after %ss", REQUEST_TIMEOUT_SECONDS)
        raise HTTPException(status_code=504, detail="The model request timed out.")
    except requests.RequestException:
        log.warning("Hugging Face chat request failed", exc_info=True)
        raise HTTPException(status_code=502, detail="The model request failed.")

    if response.status_code != 200:
        log.warning(
            "Hugging Face chat returned HTTP %s: %s",
            response.status_code,
            response.text[:500],
        )
        raise HTTPException(
            status_code=502,
            detail=f"The model provider returned HTTP {response.status_code}.",
        )

    try:
        payload = response.json()
        reply = payload["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        log.warning("Hugging Face chat returned an unexpected body")
        raise HTTPException(
            status_code=502,
            detail="The model provider returned an unexpected response.",
        )

    return {"reply": reply}
