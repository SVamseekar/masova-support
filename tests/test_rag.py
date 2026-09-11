"""Lexical SOP RAG."""

from masova_agent.knowledge.rag import search_ops_manual


def test_search_returns_relevant_chunk_with_source():
    results = search_ops_manual("cooler temperature range")
    assert len(results) > 0
    assert any(
        "haccp" in r["source"].lower() or "food_safety" in r["source"].lower() for r in results
    )


def test_search_empty_query_returns_empty_not_error():
    results = search_ops_manual("")
    assert results == []


def test_search_missing_knowledge_dir_returns_empty_not_500(monkeypatch, tmp_path):
    monkeypatch.setattr("masova_agent.knowledge.rag._KNOWLEDGE_DIR", str(tmp_path / "nonexistent"))
    results = search_ops_manual("anything")
    assert results == []


def test_search_respects_top_k():
    results = search_ops_manual("equipment", top_k=1)
    assert len(results) <= 1
