import json
import os
import re
import time
import random
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from google import genai
from google.genai import types
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
load_dotenv()

GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")).strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
GEMINI_TIMEOUT_MS = int(os.getenv("GEMINI_TIMEOUT_MS", "30000"))
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
_MISSING_API_KEYS = {"", "PASTE_YOUR_KEY_HERE", "PASTE_YOUR_GEMINI_API_KEY_HERE"}
_FREE_TIER_GEMINI_MODELS = frozenset(
    {
        "gemini-3.1-flash-lite",
        "gemini-3.1-flash",
    }
)

gemini_client = (
    genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
    )
    if GEMINI_API_KEY not in _MISSING_API_KEYS
    else None
)

BASE_DIR = Path(__file__).parent
ERROR_CODES_PATH = BASE_DIR / "error_codes.json"

with open(ERROR_CODES_PATH, "r", encoding="utf-8") as f:
    ERROR_CODES: list = json.load(f)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if GEMINI_MODEL not in _FREE_TIER_GEMINI_MODELS:
        print(f"[ERROR] {GEMINI_MODEL} is not in the approved Gemini free-tier model list.")
    elif gemini_client:
        print(f"[OK] Gemini free-tier model configured: {GEMINI_MODEL}")
    else:
        print("[ERROR] GEMINI_API_KEY is missing or not set. Please check your .env file.")
    yield


app = FastAPI(title="WhatsApp Error Lookup", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


# ---------------------------------------------------------------------------
# Startup - validate Gemini key
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ErrorRecord(BaseModel):
    meta_code: str
    karix_code: str
    category: str
    description: str


class LookupResponse(BaseModel):
    results: List[ErrorRecord]
    searched_by: str


class GenerateRequest(BaseModel):
    karix_code: str
    meta_code: str = ""
    description: str
    category: str
    client_name: str = ""


class GenerateResponse(BaseModel):
    formal1: str
    formal2: str
    technical: str


class AnalyzeRequest(BaseModel):
    karix_code: str
    meta_code: str = ""
    description: str
    category: str


class AnalyzeResponse(BaseModel):
    rca: str
    solution: str
    precaution: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_json(raw: str) -> dict:
    """Strip markdown fences if the model wraps output, then parse JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        # drop first line (```json) and last line (```)
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        raw = "\n".join(inner)
    return json.loads(raw)


def _call_ai(prompt: str, response_schema: dict) -> str:
    """Call Gemini and return raw text. Raises on any API failure."""
    if not gemini_client:
        raise ValueError("GEMINI_API_KEY is not configured in .env.")
    if GEMINI_MODEL not in _FREE_TIER_GEMINI_MODELS:
        allowed = ", ".join(sorted(_FREE_TIER_GEMINI_MODELS))
        raise ValueError(f"GEMINI_MODEL must be a Gemini free-tier model. Allowed: {allowed}.")
    max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
    backoff_base = float(os.getenv("GEMINI_BACKOFF_BASE", "1.0"))

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            # First try the common config layout
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": GEMINI_TEMPERATURE,
                },
            )
            return response.text or ""
        except Exception as first_exc:
            last_exc = first_exc
            err_str = str(first_exc)
            # If the SDK rejects `response_json_schema` inside `config`,
            # retry with a different argument layout once in this attempt.
            if "response_json_schema" in err_str or "response_json_schema" in repr(first_exc):
                try:
                    response = gemini_client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=prompt,
                        response_json_schema=response_schema,
                        response_mime_type="application/json",
                        temperature=GEMINI_TEMPERATURE,
                    )
                    return response.text or ""
                except Exception as second_exc:
                    last_exc = second_exc
                    err_str = str(second_exc)

            # Decide whether to retry: look for transient/server-side errors
            is_transient = any(x in err_str for x in ("503", "UNAVAILABLE", "UNAVAILABLE.", "Service Unavailable", "500", "5xx"))
            if attempt < max_retries - 1 and is_transient:
                sleep_for = backoff_base * (2 ** attempt) + random.uniform(0, backoff_base)
                print(f"[AI RETRY] attempt {attempt+1} failed: {err_str}. Retrying in {sleep_for:.1f}s.")
                time.sleep(sleep_for)
                continue
            # Non-transient or out of retries: raise the last exception
            raise last_exc


def _parse_ai_response(content: str, expected_fields: list[str]) -> dict:
    """Parse JSON output from the model with a fallback for malformed field values."""
    content = content.strip()

    if "```" in content:
        content = re.sub(r"```(?:json)?", "", content).strip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {}
        for field in expected_fields:
            pattern = rf'"{field}"\s*:\s*"(.*?)"(?=\s*,\s*"(?:' + "|".join(expected_fields[expected_fields.index(field) + 1:]) + r')"|\s*})'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                parsed[field] = match.group(1).replace("\\n", "\n")

        if not all(field in parsed for field in expected_fields):
            parsed = {field: content for field in expected_fields}

    for field in expected_fields:
        parsed.setdefault(field, content)

    return parsed


def _is_transient_gemini_error(exc: Exception) -> bool:
    """Heuristic to detect transient/unavailable Gemini errors.

    We look for 503/UNAVAILABLE markers in exception messages which is how
    the google-genai client surfaces model load errors seen during testing.
    """
    s = str(exc)
    return any(x in s for x in ("503", "UNAVAILABLE", "Service Unavailable", "UNAVAILABLE."))


def _is_quota_error(exc: Exception) -> bool:
    s = str(exc).upper()
    return any(x in s for x in ("429", "RESOURCE_EXHAUSTED", "QUOTA", "EXCEEDED"))



# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/lookup", response_model=LookupResponse)
async def lookup(code: str = Query(...)):
    code = code.strip()

    meta_matches = [r for r in ERROR_CODES if r["meta_code"] != "" and r["meta_code"] == code]
    if meta_matches:
        return LookupResponse(results=[ErrorRecord(**r) for r in meta_matches], searched_by="meta_code")

    karix_matches = [r for r in ERROR_CODES if r["karix_code"] == code]
    if karix_matches:
        return LookupResponse(results=[ErrorRecord(**r) for r in karix_matches], searched_by="karix_code")

    raise HTTPException(
        status_code=404,
        detail="This error code is not in the local database. Please check Meta's official documentation or escalate to L2.",
    )


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    client_name = request.client_name if request.client_name.strip() else "{Client Name}"
    meta_code = request.meta_code if request.meta_code else request.karix_code
    description = request.description
    prompt = f"""You are a WhatsApp support engineer at Karix. Write 3 different client email responses for this error.

ERROR DETAILS:
Code: {meta_code}
What it means: {description}
Client name: {client_name}

RULES FOR ALL 3 RESPONSES:
- First line must be: Hi {client_name},
- Second paragraph must explain what error {meta_code} means in simple words based on this: {description}
- Third paragraph must explain why this happened
- Fourth paragraph must explain how to prevent it
- Last line must be: If you need any further assistance, we are happy to help.
- Never say "policy violation"
- Never mention Karix internal codes
- Blank line between each paragraph
- Max 4 sentences per paragraph

RESPONSE 1 - FORMAL 1: Detailed and professional tone
RESPONSE 2 - FORMAL 2: Brief and direct, 3 sentences max per paragraph
RESPONSE 3 - TECHNICAL: For developer team, mention logs, retry logic, API actions

    Return ONLY valid JSON, no extra text, no markdown:
{{"formal1": "full response here", "formal2": "full response here", "technical": "full response here"}}"""
    try:
        content = _call_ai(
            prompt,
            {
                "type": "object",
                "properties": {
                    "formal1": {"type": "string"},
                    "formal2": {"type": "string"},
                    "technical": {"type": "string"},
                },
                "required": ["formal1", "formal2", "technical"],
            },
        )
        parsed = _parse_ai_response(content, ["formal1", "formal2", "technical"])
        if client_name and client_name.strip():
            parsed["formal1"] = parsed["formal1"].replace("{Client Name}", client_name)
            parsed["formal2"] = parsed["formal2"].replace("{Client Name}", client_name)
            parsed["technical"] = parsed["technical"].replace("{Client Name}", client_name)
        return parsed
    except Exception as e:
        if _is_quota_error(e):
            raise HTTPException(status_code=429, detail=f"Gemini quota exceeded: {str(e)[:200]}")
        if _is_transient_gemini_error(e):
            raise HTTPException(status_code=503, detail=f"Gemini temporarily unavailable: {str(e)[:200]}")
        raise HTTPException(status_code=500, detail=f"Gemini API call failed. Check your API key or try again later. ({str(e)[:200]})")


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    prompt = f"""You are a senior support engineer at Karix.

WhatsApp Error: {request.meta_code if request.meta_code else request.karix_code}
Description: {request.description}
Category: {request.category}

Give a brief technical breakdown in valid JSON only:
{{"rca": "2-3 sentences on root cause", "solution": "2-3 sentences on immediate fix", "precaution": "2-3 sentences on prevention"}}
"""
    try:
        content = _call_ai(
            prompt,
            {
                "type": "object",
                "properties": {
                    "rca": {"type": "string"},
                    "solution": {"type": "string"},
                    "precaution": {"type": "string"},
                },
                "required": ["rca", "solution", "precaution"],
            },
        )
        parsed = _parse_ai_response(content, ["rca", "solution", "precaution"])
        return parsed
    except Exception as e:
        print(f"[ANALYZE ERROR] {e}")
        if _is_quota_error(e):
            raise HTTPException(status_code=429, detail=f"Gemini quota exceeded: {str(e)[:200]}")
        if _is_transient_gemini_error(e):
            raise HTTPException(status_code=503, detail=f"Gemini temporarily unavailable: {str(e)[:200]}")
        raise HTTPException(status_code=500, detail=f"Gemini API call failed. ({str(e)[:200]})")


# ---------------------------------------------------------------------------
# Dev entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
