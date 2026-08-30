import json
import logging
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from time import sleep
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone, ServerlessSpec

from shared.config import Settings, get_settings
from shared.schemas import Document, RetrievalResult

logger = logging.getLogger("healthlink.rag")

def _embed(pc: Pinecone, model: str, texts: list[str], input_type: str) -> list[list[float]]:
    if not texts:
        return []
    batch_limit = 90
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_limit):
        batch = texts[i : i + batch_limit]
        response = pc.inference.embed(
            model=model,
            inputs=batch,
            parameters={"input_type": input_type},
        )
        all_embeddings.extend([item["values"] for item in response.data])
    return all_embeddings

class VectorStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.index_name = settings.pinecone_index_name
        self.embedding_model = settings.embedding_model
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.initialize_index()
        self.index = self.pc.Index(self.index_name)
        logger.info(
            f"Vector store connected: index={self.index_name} "
            f"model={self.embedding_model} dimension={settings.pinecone_dimension}"
        )
    def initialize_index(self) -> None:
        existing_indexes = [index.name for index in self.pc.list_indexes()]
        if self.index_name not in existing_indexes:
            logger.info(
                f"Creating Pinecone index {self.index_name} "
                f"(dimension={self.settings.pinecone_dimension})"
            )
            self.pc.create_index(
                name=self.index_name,
                dimension=self.settings.pinecone_dimension,
                metric=self.settings.pinecone_metric,
                spec=ServerlessSpec(
                    cloud=self.settings.pinecone_cloud,
                    region=self.settings.pinecone_region,
                ),
            )
            sleep(1)
    def add_documents(self, documents: list[Document]) -> None:
        if not documents:
            return
        texts = [doc.content for doc in documents]
        logger.info(f"Generating embeddings for {len(texts)} documents")
        embeddings = _embed(self.pc, self.embedding_model, texts, input_type="passage")
        vectors = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            vector_id = f"doc_{i}_{hash(doc.content) % (2**32)}"
            metadata = {"content": doc.content, **(doc.metadata or {})}
            vectors.append({"id": vector_id, "values": embedding, "metadata": metadata})
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch)
            logger.info(f"Upserted batch {i // batch_size + 1} ({len(batch)} vectors)")
        logger.info(f"Added {len(documents)} documents to Pinecone index")
    def search(self, query: str, k: int = 5) -> RetrievalResult:
        query_embedding = _embed(self.pc, self.embedding_model, [query], input_type="query")[0]
        search_results = self.index.query(
            vector=query_embedding,
            top_k=k,
            include_metadata=True,
        )
        results = []
        scores = []
        for match in search_results.matches:
            content = match.metadata.get("content", "")
            metadata = {key: val for key, val in match.metadata.items() if key != "content"}
            results.append(Document(content=content, metadata=metadata))
            scores.append(float(match.score))
        logger.info(f"Retrieved {len(results)} documents for query: {query[:50]}...")
        return RetrievalResult(documents=results, scores=scores, query=query)
    def vector_count(self) -> int:
        try:
            stats = self.index.describe_index_stats()
            return int(stats.total_vector_count)
        except Exception:
            return 0
    def get_stats(self) -> dict[str, Any]:
        stats = self.index.describe_index_stats()
        return {
            "total_vector_count": stats.total_vector_count,
            "dimension": stats.dimension,
            "index_fullness": stats.index_fullness,
        }

_vector_store: VectorStore | None = None

def get_vector_store(settings: Settings | None = None) -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(settings or get_settings())
    return _vector_store

def reset_vector_store() -> None:
    global _vector_store
    _vector_store = None

def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    return splitter.split_text(text)

def build_record_content(record: dict[str, Any]) -> str:
    parts = [
        f"Symptom: {record.get('symptom', '')}",
        f"Category: {record.get('category', '')}",
        f"Relevant specialties: {', '.join(record.get('specialty', []))}",
        f"Usual urgency: {record.get('urgency', '')}",
        f"Description: {record.get('description', '')}",
    ]
    if record.get("common_causes"):
        parts.append(f"Common causes: {', '.join(record['common_causes'])}")
    if record.get("red_flags"):
        parts.append(f"Red flags: {', '.join(record['red_flags'])}")
    if record.get("recommended_actions"):
        parts.append(f"Recommended actions: {', '.join(record['recommended_actions'])}")
    return "\n".join(part for part in parts if part.endswith(": ") is False or part)

def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())

class BM25Okapi:
    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.doc_len = [len(_tokenize(d)) for d in corpus]
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0
        self.doc_freqs: list[Counter] = []
        self.idf: dict[str, float] = {}
        self.doc_count = len(corpus)
        df: dict[str, int] = defaultdict(int)
        for doc in corpus:
            tokens = _tokenize(doc)
            freq = Counter(tokens)
            self.doc_freqs.append(freq)
            for tok in set(tokens):
                df[tok] += 1
        for tok, freq in df.items():
            self.idf[tok] = math.log((self.doc_count - freq + 0.5) / (freq + 0.5) + 1)
    def get_scores(self, query: str) -> list[float]:
        q_tokens = _tokenize(query)
        scores = [0.0] * self.doc_count
        for idx, freq in enumerate(self.doc_freqs):
            dl = self.doc_len[idx]
            for tok in q_tokens:
                if tok not in freq:
                    continue
                tf = freq[tok]
                idf = self.idf.get(tok, 0)
                denom = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl) if self.avgdl else tf + self.k1
                scores[idx] += idf * (tf * (self.k1 + 1) / denom)
        return scores
    def get_top_n(self, query: str, n: int = 5) -> list[int]:
        scores = self.get_scores(query)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [i for i in ranked if scores[i] > 0][:n]

_bm25: BM25Okapi | None = None
_bm25_docs: list[Document] = []
_chunks_path = Path("data/_chunks.json")

def _build_bm25(documents: list[Document]) -> None:
    global _bm25, _bm25_docs
    if not documents:
        _bm25 = None
        _bm25_docs = []
        return
    corpus = [d.content for d in documents]
    _bm25 = BM25Okapi(corpus)
    _bm25_docs = documents
    try:
        _chunks_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [{"content": d.content, "metadata": d.metadata} for d in documents]
        _chunks_path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to persist BM25 chunks: {e}")
    logger.info(f"BM25 index built with {len(documents)} chunks")

def _load_bm25_if_needed(settings: Settings) -> None:
    global _bm25, _bm25_docs
    if _bm25 is not None:
        return
    if _chunks_path.exists():
        try:
            payload = json.loads(_chunks_path.read_text(encoding="utf-8"))
            docs = [Document(content=p["content"], metadata=p.get("metadata", {})) for p in payload]
            corpus = [d.content for d in docs]
            _bm25 = BM25Okapi(corpus)
            _bm25_docs = docs
            logger.info(f"BM25 loaded from {_chunks_path} ({len(docs)} chunks)")
            return
        except Exception as e:
            logger.warning(f"Failed to load BM25 from {_chunks_path}: {e}")
    kb_file = getattr(settings, "kb_file", "./data/symptoms_kb.json")
    if Path(kb_file).exists():
        try:
            with open(kb_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            docs: list[Document] = []
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    content = build_record_content(item)
                    if content:
                        docs.append(Document(content=content, metadata={}))
            if docs:
                _build_bm25(docs)
        except Exception as e:
            logger.warning(f"BM25 fallback build failed: {e}")

def _bm25_search(query: str, k: int = 5) -> RetrievalResult:
    if _bm25 is None or not _bm25_docs:
        return RetrievalResult(documents=[], scores=[], query=query)
    top_idx = _bm25.get_top_n(query, n=k)
    docs = [_bm25_docs[i] for i in top_idx]
    scores = _bm25.get_scores(query)
    top_scores = [float(scores[i]) for i in top_idx]
    return RetrievalResult(documents=docs, scores=top_scores, query=query)

def _rrf_fuse(vector_res: RetrievalResult, bm25_res: RetrievalResult, k: int = 5, rrf_k: int = 60) -> RetrievalResult:
    rank_map: dict[str, float] = {}
    doc_map: dict[str, Document] = {}
    all_scores: dict[str, float] = {}
    for rank, doc in enumerate(vector_res.documents):
        key = doc.content
        doc_map[key] = doc
        rank_map[key] = rank_map.get(key, 0) + 1 / (rrf_k + rank + 1)
        all_scores[key] = vector_res.scores[rank] if rank < len(vector_res.scores) else 0
    for rank, doc in enumerate(bm25_res.documents):
        key = doc.content
        if key not in doc_map:
            doc_map[key] = doc
        rank_map[key] = rank_map.get(key, 0) + 1 / (rrf_k + rank + 1)
        if key not in all_scores:
            all_scores[key] = bm25_res.scores[rank] if rank < len(bm25_res.scores) else 0
    sorted_keys = sorted(rank_map.keys(), key=lambda x: rank_map[x], reverse=True)[:k]
    docs = [doc_map[k] for k in sorted_keys]
    scores = [rank_map[k] for k in sorted_keys]
    return RetrievalResult(documents=docs, scores=scores, query=vector_res.query or bm25_res.query)

def load_knowledge_base(file_path: str, settings: Settings) -> int:
    logger.info(f"Loading knowledge base from {file_path}")
    vector_store = get_vector_store(settings)
    docs_exist = vector_store.vector_count() > 0
    _load_bm25_if_needed(settings)
    bm25_exists = _bm25 is not None and len(_bm25_docs) > 0
    if docs_exist and bm25_exists:
        logger.info("Knowledge base already indexed (vector + BM25) - skipping")
        return 0
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    documents: list[Document] = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            content = build_record_content(item)
            metadata = {
                key: (", ".join(value) if isinstance(value, list) else value)
                for key, value in item.items()
                if key not in ("common_causes", "red_flags", "recommended_actions")
                and not isinstance(value, list)
            }
            if content:
                chunks = chunk_text(content, settings.chunk_size, settings.chunk_overlap)
                for chunk in chunks:
                    documents.append(Document(content=chunk, metadata=metadata))
    elif isinstance(data, dict):
        for key, value in data.items():
            content = value if isinstance(value, str) else json.dumps(value)
            documents.append(Document(content=content, metadata={"source": key}))
    _build_bm25(documents)
    if not docs_exist:
        vector_store.add_documents(documents)
    else:
        logger.info("Vector store already has vectors - BM25 refreshed only")
    logger.info(f"Loaded {len(documents)} document chunks into hybrid store")
    return len(documents)

def retrieve_relevant_docs(query: str, k: int = 5, settings: Settings | None = None) -> RetrievalResult:
    if settings is None:
        settings = get_settings()
    _load_bm25_if_needed(settings)
    vector_k = 10
    bm25_k = 10
    try:
        vector_store = get_vector_store(settings)
        vector_res = vector_store.search(query, k=vector_k)
    except Exception as e:
        logger.warning(f"Vector search failed, falling back to BM25: {e}")
        vector_res = RetrievalResult(documents=[], scores=[], query=query)
    bm25_res = _bm25_search(query, k=bm25_k)
    if not vector_res.documents and not bm25_res.documents:
        return RetrievalResult(documents=[], scores=[], query=query)
    if not vector_res.documents:
        return RetrievalResult(documents=bm25_res.documents[:k], scores=bm25_res.scores[:k], query=query)
    if not bm25_res.documents:
        return RetrievalResult(documents=vector_res.documents[:k], scores=vector_res.scores[:k], query=query)
    fused = _rrf_fuse(vector_res, bm25_res, k=k, rrf_k=60)
    logger.info(f"Hybrid retrieved {len(fused.documents)} docs (vector {len(vector_res.documents)} + bm25 {len(bm25_res.documents)} -> fused {len(fused.documents)})")
    return fused

def format_retrieval_context(retrieval_result: RetrievalResult, max_docs: int = 3) -> str:
    if not retrieval_result.documents:
        return ""
    context_parts = ["Relevant medical knowledge:"]
    for i, doc in enumerate(retrieval_result.documents[:max_docs]):
        context_parts.append(f"\n[Source {i + 1}]")
        context_parts.append(doc.content)
        if doc.metadata:
            context_parts.append(f"Metadata: {json.dumps(doc.metadata)}")
    return "\n".join(context_parts)
