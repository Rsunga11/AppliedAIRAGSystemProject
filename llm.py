"""Optional Gemini step for the Care Advisor.

If GEMINI_API_KEY is set (in the environment or a git-ignored .env file), Gemini rewrites the
retrieved snippets into a short, friendly answer. If the key is missing, the request fails, the
free tier is rate-limited, or the reply looks unsafe, explain() returns None and the advisor
falls back to its offline answer. The API key is sent in a request header and is never logged.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import List, Optional

logger = logging.getLogger("pawpal")

DEFAULT_MODEL = "gemini-2.0-flash"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_ANSWER_CHARS = 600
# Reject model output that sounds like medical advice (a second guardrail after the input check).
UNSAFE_OUTPUT = re.compile(r"\b(\d+\s?(mg|ml|milligrams?)|dosage|dose of|diagnos\w+|prescri\w+)\b", re.IGNORECASE)

PROMPT_TEMPLATE = """You are PawPal+, a careful pet-care scheduling assistant.
Answer the owner's question using ONLY the notes below. Rules:
- If the notes do not answer the question, say you are not sure and suggest asking a veterinarian.
- Never give medication dosages or diagnose illnesses.
- Be friendly and keep it under 80 words.

Notes:
{notes}

Question: {question}
Answer:"""


def load_dotenv(path: str = ".env") -> None:
    """Load KEY=VALUE lines from a .env file into os.environ (existing variables win)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class GeminiClient:
    """Tiny Gemini REST client using only the standard library."""

    def __init__(self, api_key: str, model: Optional[str] = None, timeout: float = 15.0, opener=None):
        self._api_key = api_key  # private: never printed or logged
        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen

    def explain(self, question: str, snippets: List[str]) -> Optional[str]:
        """Return a short answer grounded in `snippets`, or None if anything goes wrong."""
        notes = "\n".join(f"- {s}" for s in snippets)
        body = json.dumps(
            {
                "contents": [{"parts": [{"text": PROMPT_TEMPLATE.format(notes=notes, question=question)}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            API_URL.format(model=self.model),
            data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": self._api_key},
            method="POST",
        )
        try:
            with self._open(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as error:  # includes 429 rate limits and 400/403 bad key
            logger.warning("gemini request failed: HTTP %s (falling back to offline answer)", error.code)
            return None
        except Exception as error:  # network down, timeout, bad JSON, unexpected shape
            logger.warning("gemini request failed: %s (falling back to offline answer)", type(error).__name__)
            return None

        if not text or UNSAFE_OUTPUT.search(text):
            logger.warning("gemini answer rejected by output guardrail (falling back to offline answer)")
            return None
        return text[:MAX_ANSWER_CHARS]


def from_env() -> Optional[GeminiClient]:
    """Return a GeminiClient if GEMINI_API_KEY is configured, otherwise None (offline mode)."""
    load_dotenv()
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return GeminiClient(key) if key else None
