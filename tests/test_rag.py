import json

from app.rag import (
    _bm25_search,
    _build_bm25,
    _rrf_fuse,
    _tokenize,
    build_record_content,
    chunk_text,
    format_retrieval_context,
    load_knowledge_base,
)
from shared.schemas import Document, RetrievalResult


def test_chunk_text_splits():
    text = "a " * 600
    chunks = chunk_text(text, chunk_size=500, chunk_overlap=50)
    assert len(chunks) >= 2
    assert all(len(c) <= 500 for c in chunks)


def test_build_record_content():
    rec = {"symptom": "Headache", "category": "neurological", "specialty": ["Neurology"], "urgency": "routine", "description": "Pain", "common_causes": ["Stress"], "red_flags": ["vision"], "recommended_actions": ["Rest"]}
    content = build_record_content(rec)
    assert "Headache" in content
    assert "Neurology" in content
    assert "Stress" in content


def test_tokenize():
    assert _tokenize("Headache AND Fever!") == ["headache", "and", "fever"]


def test_bm25_ranking():
    docs = [Document(content="headache and fever", metadata={}), Document(content="chest pain and cough", metadata={}), Document(content="headache with nausea", metadata={})]
    _build_bm25(docs)
    res = _bm25_search("headache", k=2)
    assert len(res.documents) == 2
    assert all("headache" in d.content for d in res.documents)
    assert res.scores[0] >= res.scores[1]


def test_rrf_fuse():
    docs = [Document(content="a", metadata={}), Document(content="b", metadata={}), Document(content="c", metadata={})]
    v = RetrievalResult(documents=[docs[0], docs[1]], scores=[0.9, 0.8], query="q")
    b = RetrievalResult(documents=[docs[2], docs[0]], scores=[1.2, 0.5], query="q")
    fused = _rrf_fuse(v, b, k=2, rrf_k=60)
    assert len(fused.documents) == 2
    assert fused.documents[0].content == "a"
    assert fused.scores[0] > fused.scores[1]


def test_format_retrieval_context():
    res = RetrievalResult(documents=[Document(content="hello", metadata={"a": "1"})], scores=[1.0], query="q")
    ctx = format_retrieval_context(res, max_docs=1)
    assert "hello" in ctx
    assert "Source 1" in ctx


def test_format_empty():
    assert format_retrieval_context(RetrievalResult(documents=[], scores=[], query="q")) == ""


def test_load_knowledge_base_creates_bm25(tmp_path, monkeypatch):
    from app import rag
    monkeypatch.setattr(rag, "_chunks_path", tmp_path / "_chunks.json")
    # mock vector store
    class DummyVS:
        def vector_count(self): return 0
        def add_documents(self, docs): self.added = len(docs)
    monkeypatch.setattr(rag, "get_vector_store", lambda s=None: DummyVS())
    # minimal KB
    kb = tmp_path / "kb.json"
    kb.write_text(json.dumps([{"symptom": "Test", "category": "general", "specialty": ["General Practice"], "urgency": "routine", "description": "Desc"}]), encoding="utf-8")
    from shared.config import get_settings
    n = load_knowledge_base(str(kb), get_settings())
    assert n > 0
    assert (tmp_path / "_chunks.json").exists()
