"""Regenerate every pasted output in the docs from the code, so the evidence cannot drift.

Run: python generate_evidence.py     (run it as the last step before committing)

It re-runs main.py, the evaluation harness and pytest, then rewrites the fenced blocks in README.md,
ai_interactions.md and model_card.md that sit between <!-- BEGIN:name --> and <!-- END:name --> markers.
It does not call Gemini; style_comparison.py (live) writes logs/style_comparison.txt, which is embedded if present.
"""

import contextlib
import io
import os
import subprocess
import sys

import eval_harness
import main as demo
from advisor import CareAdvisor
from agent import format_trace, trace_to_json
from retriever import KnowledgeBase

PROJECT = os.path.dirname(os.path.abspath(__file__))


def between(text: str, start: str, end: str = None) -> str:
    a = text.index(start)
    b = text.index(end, a + len(start)) if end else len(text)
    return text[a:b].strip()


def set_block(text: str, anchor: str, name: str, content: str, lang: str = "") -> str:
    """Put `content` in a fenced block between BEGIN/END markers (creating the markers on first use)."""
    begin, end = f"<!-- BEGIN:{name} -->", f"<!-- END:{name} -->"
    block = f"{begin}\n```{lang}\n{content.rstrip()}\n```\n{end}"
    if begin in text:
        a = text.index(begin)
        b = text.index(end, a) + len(end)
        return text[:a] + block + text[b:]
    anchor_at = text.index(anchor)
    fence_start = text.index("```", anchor_at)
    fence_end = text.index("\n```", fence_start + 3) + 4
    return text[:fence_start] + block + text[fence_end:]


def read(path: str) -> str:
    return open(os.path.join(PROJECT, path), encoding="utf-8", newline="").read().replace("\r\n", "\n")


def write(path: str, text: str) -> None:
    open(os.path.join(PROJECT, path), "w", encoding="utf-8", newline="\n").write(text)


def main() -> None:
    os.chdir(PROJECT)
    # --- the CLI demo (also records the Rex agent result)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        demo.main()
    cli = buffer.getvalue()
    rag = between(cli, "== RAG: questions answered from the knowledge base ==", "== Guardrails ==")
    guard = between(cli, "== Guardrails ==", "== RAG-backed review of a task ==")
    review = between(cli, "== RAG-backed review of a task ==", "== Agent: plan -> act -> check -> re-plan (proposals only) ==")
    agent_section = between(cli, "== Agent: plan -> act -> check -> re-plan (proposals only) ==")
    trace_json = trace_to_json(demo.LAST_AGENT_RESULT)
    unfixable = format_trace(demo.demo_unfixable_run(CareAdvisor(KnowledgeBase())))

    # --- evaluation harness (writes logs/eval_results.txt itself)
    with contextlib.redirect_stdout(io.StringIO()):
        eval_harness.main()
    eval_text = read("logs/eval_results.txt").strip()

    # --- pytest
    result = subprocess.run([sys.executable, "-m", "pytest", "-q"], capture_output=True, text=True)
    pytest_text = result.stdout.strip()
    write("logs/pytest_results.txt", pytest_text + "\n")

    readme = read("README.md")
    readme = set_block(readme, "## Architecture overview", "architecture", read("diagrams/architecture.mmd").strip(), "mermaid")
    readme = set_block(readme, "### 1. RAG", "rag", rag)
    readme = set_block(readme, "### 2. Guardrails", "guardrails", guard)
    readme = set_block(readme, "### 3. RAG-backed", "review", review)
    readme = set_block(readme, "### 4. Agent", "agent", agent_section)
    readme = set_block(readme, "saves the output to [`logs/eval_results.txt`]", "eval", eval_text)
    readme = set_block(readme, "`python -m pytest`:", "pytest", pytest_text)
    style_path = os.path.join(PROJECT, "logs", "style_comparison.txt")
    if os.path.exists(style_path):
        style = read("logs/style_comparison.txt").strip()
        summary = style[style.index("Summary (computed by code)"):]
        readme = set_block(readme, "Summary of the comparison", "style_summary", summary)
    write("README.md", readme)

    ai = read("ai_interactions.md")
    ai = set_block(ai, "### Trace 1", "trace1", agent_section)
    ai = set_block(ai, "### Trace 2", "trace2", unfixable)
    ai = set_block(ai, "### Trace 3", "trace3", trace_json, "json")
    write("ai_interactions.md", ai)

    if os.path.exists(style_path):
        card = read("model_card.md")
        card = set_block(card, "Full output of `python style_comparison.py`", "style_full", style)
        write("model_card.md", card)

    print("Regenerated README.md, ai_interactions.md, model_card.md and logs/ from the code.")
    print(pytest_text.splitlines()[-1])


if __name__ == "__main__":
    main()
