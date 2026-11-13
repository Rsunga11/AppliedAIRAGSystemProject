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

# A "-latest" alias survives model renames; older names (e.g. gemini-2.0-flash) return 404 for new keys.
# Override with GEMINI_MODEL. Any failure falls back to the offline answer.
DEFAULT_MODEL = "gemini-flash-lite-latest"
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

# ---------------------------------------------------------------- specialized style
# "Specialization" here means few-shot prompting plus a strict output contract (no fine-tuning).
# The specialized PawPal Coach answers in exactly this shape, so the app's tone is consistent:
#     Answer: <one plain sentence using only facts from the notes> Tip: <one short practical sentence>
SPECIALIZED_TEMPLATE = """You are PawPal Coach, a calm, no-nonsense pet-care scheduling coach.
Reply in EXACTLY this format, on a single line:
Answer: <one plain sentence using only facts from the notes> Tip: <one short, practical scheduling tip>

Hard rules:
- Use ONLY facts that appear in the notes. If they don't answer the question, write: Answer: I'm not sure, so please ask a veterinarian. Tip: Check a trusted pet-care source.
- No greetings, no exclamation marks, no emojis, at most 45 words in total.
- Never give medication dosages or diagnose illnesses.

Example 1
Notes:
- Adult dogs are usually fed twice a day, about 8 to 12 hours apart. Feeding takes 10 to 15 minutes including fresh water.
Question: How often should I feed my dog?
Reply: Answer: Adult dogs are usually fed twice a day, about 8 to 12 hours apart. Tip: Block 10 to 15 minutes for each meal, with fresh water.

Example 2
Notes:
- Scoop the litter box at least once a day and fully change the litter weekly. A scoop takes 5 to 10 minutes.
Question: How often should I clean the litter box?
Reply: Answer: Scoop the litter box at least once a day and change the litter fully every week. Tip: Add a daily 5 to 10 minute scoop reminder.

Example 3
Notes:
- Healthy adult cats should see a vet at least once a year.
Question: Should I get a pet insurance plan?
Reply: Answer: I'm not sure, so please ask a veterinarian. Tip: Check a trusted pet-care source.

Now the real one.
Notes:
{notes}

Question: {question}
Reply:"""

STYLES = {"baseline": PROMPT_TEMPLATE, "specialized": SPECIALIZED_TEMPLATE}
MAX_SPECIALIZED_WORDS = 45
GREETING = re.compile(r"^\s*(hello|hi|hey|hiya|greetings|good (morning|afternoon|evening))\b", re.IGNORECASE)
SPECIALIZED_FORMAT = re.compile(r"^Answer: .+? Tip: .+$", re.DOTALL)


def conforms_to_specialized_style(text: str) -> bool:
    """True if `text` follows the PawPal Coach contract: one Answer + Tip line, no greeting, no '!', <= 45 words."""
    return bool(
        SPECIALIZED_FORMAT.match(text.strip())
        and "\n" not in text.strip()
        and "!" not in text
        and not GREETING.match(text)
        and len(text.split()) <= MAX_SPECIALIZED_WORDS
    )


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

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        timeout: float = 15.0,
        opener=None,
        style: str = "specialized",
    ):
        if style not in STYLES:
            raise ValueError(f"style must be one of {sorted(STYLES)}")
        self.style = style  # "baseline" = plain prompt, "specialized" = few-shot PawPal Coach
        self._api_key = api_key  # private: never printed or logged
        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen

    def explain(self, question: str, snippets: List[str], enforce_style: bool = True) -> Optional[str]:
        """Return a short answer grounded in `snippets`, or None if anything goes wrong.

        In "specialized" style the reply must follow the PawPal Coach format; if it doesn't and
        `enforce_style` is True, None is returned so the advisor uses its offline answer instead.
        (The comparison script passes enforce_style=False to measure raw compliance.)
        """
        notes = "\n".join(f"- {s}" for s in snippets)
        body = json.dumps(
            {
                "contents": [{"parts": [{"text": STYLES[self.style].format(notes=notes, question=question)}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
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
        if self.style == "specialized" and enforce_style and not conforms_to_specialized_style(text):
            logger.warning("gemini answer broke the specialized style contract (falling back to offline answer)")
            return None
        return text[:MAX_ANSWER_CHARS]


def from_env() -> Optional[GeminiClient]:
    """Return a GeminiClient if GEMINI_API_KEY is configured, otherwise None (offline mode)."""
    load_dotenv()
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return GeminiClient(key) if key else None
