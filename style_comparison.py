"""Baseline vs specialized (few-shot) Gemini output, on the same retrieved notes.

Run: python style_comparison.py     (needs GEMINI_API_KEY in .env or the environment)

For each question the advisor's retriever picks the notes; then the SAME notes are sent once with
the plain "baseline" prompt and once with the few-shot "specialized" PawPal Coach prompt. Metrics
are computed by code (not by eye) and the result is written to logs/style_comparison.txt.
"""

import os
import re
import sys
import time

from eval_harness import QA_CASES
from llm import GeminiClient, conforms_to_specialized_style, from_env
from retriever import KnowledgeBase

RESULTS_PATH = os.path.join("logs", "style_comparison.txt")
GREETING = re.compile(r"^\s*(hello|hi|hey|hiya|greetings)\b", re.IGNORECASE)
NUMBER = re.compile(r"\d+")


def metrics(text: str, notes: str) -> dict:
    """Measurable properties of one answer."""
    words = len(text.split())
    answer_numbers = set(NUMBER.findall(text))
    note_numbers = set(NUMBER.findall(notes))
    return {
        "words": words,
        "greeting": bool(GREETING.match(text)),
        "exclamations": text.count("!"),
        "format_ok": conforms_to_specialized_style(text),
        "grounded_numbers": answer_numbers <= note_numbers,
    }


def ask_with_retry(client: GeminiClient, question: str, snippets: list, attempts: int = 4):
    """Call Gemini, retrying a few times because the free tier sometimes returns 503/429."""
    for attempt in range(attempts):
        text = client.explain(question, snippets, enforce_style=False)
        if text:
            return text
        time.sleep(3 * (attempt + 1))
    return None


def run() -> list:
    base_client = from_env()
    if base_client is None:
        return ["No GEMINI_API_KEY found. Add it to .env to run this comparison (it needs a live model)."]
    key = base_client._api_key  # reuse the loaded key without ever printing it
    baseline = GeminiClient(key, model=base_client.model, style="baseline")
    special = GeminiClient(key, model=base_client.model, style="specialized")
    kb = KnowledgeBase()

    lines = [f"Baseline vs specialized prompt: model {base_client.model}, same retrieved notes, {len(QA_CASES)} questions", "=" * 100]
    totals = {"baseline": [], "specialized": []}
    for question, species, _fact, _source in QA_CASES:
        hits = kb.search(question, k=3, species=species)
        snippets = [h.chunk.text for h in hits]
        notes = " ".join(snippets)
        outputs = {"baseline": ask_with_retry(baseline, question, snippets), "specialized": ask_with_retry(special, question, snippets)}
        lines.append(f"Q: {question}")
        for style, text in outputs.items():
            if text is None:
                lines.append(f"  [{style:<11}] (no reply after retries)")
                continue
            m = metrics(text, notes)
            totals[style].append(m)
            lines.append(f"  [{style:<11}] {text}")
            lines.append(
                f"  {'':<13} words={m['words']} greeting={m['greeting']} exclamations={m['exclamations']} "
                f"format_ok={m['format_ok']} grounded_numbers={m['grounded_numbers']}"
            )
        lines.append("")

    lines.append("Summary (computed by code)")
    lines.append(f"{'metric':<34}{'baseline':>12}{'specialized':>14}")
    lines.append("-" * 60)

    def summarize(name, fn):
        row = []
        for style in ("baseline", "specialized"):
            rows = totals[style]
            row.append(fn(rows) if rows else "n/a")
        lines.append(f"{name:<34}{row[0]:>12}{row[1]:>14}")

    summarize("answers received", lambda r: f"{len(r)}/{len(QA_CASES)}")
    summarize("average words", lambda r: f"{sum(x['words'] for x in r) / len(r):.1f}")
    summarize("answers starting with a greeting", lambda r: f"{sum(x['greeting'] for x in r)}/{len(r)}")
    summarize("answers with an exclamation mark", lambda r: f"{sum(x['exclamations'] > 0 for x in r)}/{len(r)}")
    summarize("follow the Answer/Tip format", lambda r: f"{sum(x['format_ok'] for x in r)}/{len(r)}")
    summarize("numbers all found in the notes", lambda r: f"{sum(x['grounded_numbers'] for x in r)}/{len(r)}")
    return lines


def main() -> int:
    lines = run()
    text = "\n".join(lines)
    print(text)
    if not lines[0].startswith("No GEMINI_API_KEY"):
        os.makedirs("logs", exist_ok=True)
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"\nSaved to {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
