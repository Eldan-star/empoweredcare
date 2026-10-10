import os
import threading
import time
from collections import deque
import httpx
import PIL.Image
from google import genai
from google.genai import errors as genai_errors
import io
from pathlib import Path
from dotenv import load_dotenv
from config import GEMINI_MODEL_PREFERENCES, GEMINI_RPM, GEMINI_CALL_BUDGET_SECONDS

load_dotenv()

# Overload / server-side hiccups that usually clear within seconds.
TEMPORARY_STATUS_CODES = {500, 502, 503, 504}
MAX_ATTEMPTS_PER_MODEL = 4
# A per-minute limit asks us to wait seconds; longer waits (daily limits) skip the model instead.
MAX_RATE_LIMIT_WAIT = 60


class AIQuotaExhausted(RuntimeError):
    """Every model in GEMINI_MODELS is out of quota or rate-limited right now."""


def _format_wait(seconds: float) -> str:
    minutes = max(1, round(seconds / 60))
    return f"{minutes // 60} h {minutes % 60} min" if minutes >= 60 else f"{minutes} min"


def _quota_info(e: Exception):
    """(seconds Google asks us to wait or None, whether a daily quota is exhausted)."""
    details = getattr(e, "details", None)
    items = (details.get("error") or {}).get("details") or [] if isinstance(details, dict) else []
    delay, daily = None, False
    for item in items:
        kind = item.get("@type", "")
        if kind.endswith("RetryInfo"):
            try:
                delay = float(str(item.get("retryDelay", "")).rstrip("s"))
            except ValueError:
                pass
        elif kind.endswith("QuotaFailure"):
            daily = daily or any("PerDay" in v.get("quotaId", "") for v in item.get("violations", []))
    return delay, daily


class _Pacer:
    """Keeps each model under `rpm` requests per rolling minute (0 = no pacing)."""

    def __init__(self, rpm: int):
        self.rpm = rpm
        self.sent: dict[str, deque] = {}
        self.lock = threading.Lock()

    def acquire(self, model: str, deadline: float) -> bool:
        """Wait for a free slot; False if none frees up before `deadline`."""
        if self.rpm <= 0:
            return True
        while True:
            with self.lock:
                now = time.monotonic()
                q = self.sent.setdefault(model, deque())
                while q and now - q[0] >= 60:
                    q.popleft()
                if len(q) < self.rpm:
                    q.append(now)
                    return True
                wait = 60 - (now - q[0]) + 0.1
            if now + wait > deadline:
                return False
            print(f"⏳ Pacing: {model} is at {self.rpm} requests/minute. Waiting {wait:.0f} s...")
            time.sleep(wait)


class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("❌ GEMINI_API_KEY not found in .env file")
        
        self.client = genai.Client(api_key=self.api_key)

        # Tried in order; set GEMINI_MODELS in .env when Google retires a model.
        self.models = GEMINI_MODEL_PREFERENCES
        self._pacer = _Pacer(GEMINI_RPM)
        # model -> time.monotonic() when its quota is expected back
        self._out_of_quota_until: dict[str, float] = {}

    def _generate(self, model_name: str, contents) -> str:
        """One generate_content call; returns the reply text or raises."""
        response = self.client.models.generate_content(model=model_name, contents=contents)
        if not response.text:
            raise ValueError("Empty response")
        return response.text

    @staticmethod
    def _is_rate_limit(e: Exception) -> bool:
        return (isinstance(e, genai_errors.APIError) and e.code == 429) or "429" in str(e)

    @staticmethod
    def _is_temporary(e: Exception) -> bool:
        """Overload or dropped connection: worth retrying the same model."""
        if isinstance(e, genai_errors.APIError):
            return e.code in TEMPORARY_STATUS_CODES
        return isinstance(e, httpx.TransportError)

    def _call(self, contents, label: str, parse=lambda text: text):
        """
        Try each model in GEMINI_MODELS in order, within GEMINI_CALL_BUDGET_SECONDS.
        - Per-minute limit (429): wait as long as Google asks, then retry the same model.
        - Daily limit or a long wait: remember the model is out of quota until it resets
          and move on immediately.
        - Temporary error (503, dropped connection, ...): retry after 2, 4, then 8 s.
        - Anything else, including a bad reply that `parse` rejects: next model.
        Raises AIQuotaExhausted when quota limits are the only reason every model failed.
        """
        deadline = time.monotonic() + GEMINI_CALL_BUDGET_SECONDS
        last_error, quota_only = None, True
        for model_name in self.models:
            cooling = self._out_of_quota_until.get(model_name, 0) - time.monotonic()
            if cooling > 0:
                print(f"⏭️ Skipping {model_name}: out of quota for about {_format_wait(cooling)}.")
                last_error = last_error or f"{model_name} is out of quota"
                continue
            for attempt in range(MAX_ATTEMPTS_PER_MODEL):
                if not self._pacer.acquire(model_name, deadline):
                    last_error = f"{model_name} has no free request slot within the time budget"
                    break
                try:
                    print(f"🧠 {label}: Using {model_name}...")
                    return parse(self._generate(model_name, contents))
                except Exception as e:
                    print(f"⚠️ {model_name} {label} error (attempt {attempt + 1}): {e}")
                    last_error = e
                    last_attempt = attempt == MAX_ATTEMPTS_PER_MODEL - 1
                    if self._is_rate_limit(e):
                        delay, daily = _quota_info(e)
                        delay = 30.0 if delay is None else delay
                        if daily or delay > MAX_RATE_LIMIT_WAIT or last_attempt \
                                or time.monotonic() + delay > deadline:
                            self._out_of_quota_until[model_name] = time.monotonic() + delay
                            print(f"⏭️ {model_name} is out of quota for about {_format_wait(delay)}; trying the next model.")
                            break
                        print(f"⏳ {model_name} per-minute limit reached. Waiting {delay:.0f} s as Google asks...")
                        time.sleep(delay + 0.5)
                        continue
                    quota_only = False
                    wait = 2 ** (attempt + 1)
                    if self._is_temporary(e) and not last_attempt and time.monotonic() + wait < deadline:
                        print(f"⏳ Gemini is busy or the connection dropped. Retrying in {wait} seconds...")
                        time.sleep(wait)
                        continue
                    break
        if quota_only:
            waits = [t - time.monotonic() for t in self._out_of_quota_until.values() if t > time.monotonic()]
            back = f" The first model should be available again in about {_format_wait(min(waits))}." if waits else ""
            raise AIQuotaExhausted(
                "AI quota reached: every Gemini model in GEMINI_MODELS is rate-limited or out of "
                f"quota.{back} Try again later, add another model to GEMINI_MODELS, or raise the "
                "quota (billing) in Google AI Studio."
            )
        raise ValueError(f"❌ Gemini {label.lower()} failed: {last_error}")

    @staticmethod
    def _strip_fences(raw_text: str) -> str:
        if "```json" in raw_text:
            return raw_text.split("```json")[1].split("```")[0].strip()
        if "```" in raw_text:
            return raw_text.split("```")[1].split("```")[0].strip()
        return raw_text.strip()

    def generate_text(self, prompt: str) -> str:
        """Generate text response using Gemini for text-only prompts."""
        return self._call(prompt, "Text Generation", parse=self._strip_fences)

    def generate_vision_text(self, image_path_or_bytes, prompt: str) -> str:
        """Extract text from an image using Gemini Vision."""
        if isinstance(image_path_or_bytes, (str, Path)):
            img = PIL.Image.open(image_path_or_bytes)
        else:
            img = PIL.Image.open(io.BytesIO(image_path_or_bytes))
            
        return self._call([prompt, img], "Vision Scan", parse=str.strip)
