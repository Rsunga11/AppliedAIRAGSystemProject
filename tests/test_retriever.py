import pytest

from retriever import KnowledgeBase, parse_document, tokenize


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase()


def test_parse_document_splits_chunks_and_reads_hints():
    raw = """# Title

## Walks
species: dog
topic: walk
recommended_minutes: 30-60

Dogs need walks every day.

## No hints
Plain text only.
"""
    chunks = parse_document("x.md", raw)
    assert [c.title for c in chunks] == ["Walks", "No hints"]
    assert chunks[0].meta == {"species": "dog", "topic": "walk", "recommended_minutes": "30-60"}
    assert chunks[0].text == "Dogs need walks every day."
    assert chunks[1].meta == {}


def test_tokenize_drops_stopwords_and_stems():
    assert tokenize("The dogs are walking") == ["dog", "walk"]


def test_knowledge_base_loads_multiple_sources(kb):
    sources = {c.source for c in kb.chunks}
    assert len(sources) >= 4
    assert len(kb.chunks) >= 15


def test_walk_query_finds_dog_walk_section(kb):
    hits = kb.search("how long should I walk my dog", k=1, species="dog")
    assert hits[0].chunk.title == "Dog walks and exercise"
    assert 0 < hits[0].score <= 1


def test_species_filter_prefers_matching_species(kb):
    dog = kb.search("feeding times", k=1, species="dog")[0]
    cat = kb.search("feeding times", k=1, species="cat")[0]
    assert dog.chunk.meta["species"] == "dog"
    assert cat.chunk.meta["species"] == "cat"


def test_off_topic_or_empty_query_returns_nothing(kb):
    assert kb.search("quantum physics homework") == []
    assert kb.search("") == []
    assert kb.search("the of and") == []  # only stopwords


def test_for_species_topic_lookup_and_any_fallback(kb):
    assert kb.for_species_topic("dog", "walk").meta["recommended_minutes"] == "30-60"
    assert kb.for_species_topic("cat", "medication").meta["species"] == "any"
    assert kb.for_species_topic("dog", "nonexistent") is None


def test_missing_directory_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        KnowledgeBase(str(tmp_path / "nope"))
    with pytest.raises(ValueError):
        KnowledgeBase(str(tmp_path))  # exists but has no documents
