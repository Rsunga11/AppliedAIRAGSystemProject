import io
import json
import logging
import urllib.error

import pytest

import llm
from advisor import CareAdvisor
from llm import GeminiClient, from_env, load_dotenv
from retriever import KnowledgeBase

SECRET = "AIza-super-secret-test-key"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def reply(text):
    payload = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return FakeResponse(json.dumps(payload).encode("utf-8"))


def client_returning(text):
    return GeminiClient(SECRET, opener=lambda request, timeout: reply(text))


def test_successful_call_returns_text_and_sends_key_only_in_header():
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["key_header"] = request.get_header("X-goog-api-key")
        seen["prompt"] = json.loads(request.data)["contents"][0]["parts"][0]["text"]
        return reply("Walk your dog about 30 to 60 minutes a day.")

    client = GeminiClient(SECRET, opener=opener)
    text = client.explain("How long should I walk my dog?", ["Most adult dogs need 30 to 60 minutes."])
    assert text == "Walk your dog about 30 to 60 minutes a day."
    assert seen["key_header"] == SECRET
    assert SECRET not in seen["url"]  # never in the URL
    assert "Most adult dogs need 30 to 60 minutes." in seen["prompt"]  # grounded in the retrieved notes
    assert "ONLY the notes" in seen["prompt"]


@pytest.mark.parametrize("status", [400, 403, 429, 500])
def test_http_errors_return_none(status):
    def opener(request, timeout):
        raise urllib.error.HTTPError(request.full_url, status, "error", {}, None)

    assert GeminiClient(SECRET, opener=opener).explain("q", ["note"]) is None


def test_network_errors_and_bad_json_return_none():
    def timeout(request, timeout):
        raise TimeoutError("slow")

    def garbage(request, timeout):
        return FakeResponse(b"not json")

    def wrong_shape(request, timeout):
        return FakeResponse(b'{"candidates": []}')

    for opener in (timeout, garbage, wrong_shape):
        assert GeminiClient(SECRET, opener=opener).explain("q", ["note"]) is None


@pytest.mark.parametrize("unsafe", ["Give 200 mg twice a day.", "The dosage is small.", "That sounds like a diagnosis."])
def test_unsafe_model_output_is_rejected(unsafe):
    assert client_returning(unsafe).explain("q", ["note"]) is None


def test_empty_output_is_rejected_and_long_output_is_trimmed():
    assert client_returning("   ").explain("q", ["note"]) is None
    assert len(client_returning("word " * 500).explain("q", ["note"])) <= llm.MAX_ANSWER_CHARS


def test_api_key_never_appears_in_logs(caplog):
    def opener(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 403, "forbidden", {}, None)

    with caplog.at_level(logging.DEBUG, logger="pawpal"):
        GeminiClient(SECRET, opener=opener).explain("q", ["note"])
    assert SECRET not in caplog.text
    assert "HTTP 403" in caplog.text


def test_from_env_is_none_without_a_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env here
    assert from_env() is None


def test_from_env_reads_key_and_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(f'# comment\nGEMINI_API_KEY="{SECRET}"\n', encoding="utf-8")
    client = from_env()
    assert isinstance(client, GeminiClient)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)  # clean up what load_dotenv set


def test_existing_environment_variable_wins_over_dotenv(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    (tmp_path / ".env").write_text("GEMINI_API_KEY=from-file\n", encoding="utf-8")
    load_dotenv(str(tmp_path / ".env"))
    import os

    assert os.environ["GEMINI_API_KEY"] == "from-env"


def test_advisor_uses_gemini_text_when_it_works_and_falls_back_when_it_fails():
    kb = KnowledgeBase()
    good = CareAdvisor(kb, llm=client_returning("Aim for 30 to 60 minutes of walking a day."))
    answer = good.answer_question("How long should I walk my dog?", "dog")
    assert answer.used_llm and answer.text.startswith("Aim for")

    def failing(request, timeout):
        raise TimeoutError("no network")

    bad = CareAdvisor(kb, llm=GeminiClient(SECRET, opener=failing))
    fallback = bad.answer_question("How long should I walk my dog?", "dog")
    assert not fallback.used_llm and "30 to 60 minutes" in fallback.text  # offline answer still works


def test_medical_questions_never_reach_the_llm():
    calls = []

    def opener(request, timeout):
        calls.append(request)
        return reply("anything")

    advisor = CareAdvisor(KnowledgeBase(), llm=GeminiClient(SECRET, opener=opener))
    assert advisor.answer_question("What dosage of ibuprofen can my dog have?").refused
    assert calls == []  # the guardrail runs before any model call
