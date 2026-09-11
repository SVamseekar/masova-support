"""Lexical SOP retrieval: heading-chunked markdown, keyword-overlap scoring."""

from __future__ import annotations

import os
import re

_KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", "data/knowledge")
_STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for"}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _chunk_file(path: str) -> list[dict]:
    with open(path, "r") as f:
        content = f.read()
    sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)
    return [{"source": os.path.basename(path), "chunk": s.strip()} for s in sections if s.strip()]


def _load_chunks() -> list[dict]:
    if not os.path.isdir(_KNOWLEDGE_DIR):
        return []
    chunks = []
    for fname in os.listdir(_KNOWLEDGE_DIR):
        if fname.endswith(".md"):
            chunks.extend(_chunk_file(os.path.join(_KNOWLEDGE_DIR, fname)))
    return chunks


def search_ops_manual(query: str, top_k: int = 3) -> list[dict]:
    if not query or not str(query).strip():
        return []
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []
    scored = []
    for chunk in _load_chunks():
        chunk_tokens = _tokenize(chunk["chunk"])
        overlap = len(query_tokens & chunk_tokens)
        if overlap > 0:
            scored.append({**chunk, "score": overlap / len(query_tokens)})
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_k]
