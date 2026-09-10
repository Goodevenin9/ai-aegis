"""Local-first hybrid retrieval with citations and measurable quality."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

_TOKEN = re.compile(r"[a-zA-Z0-9_./:-]+|[\u4e00-\u9fff]")


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in _TOKEN.findall(text)]


def _vector(text: str, dimensions: int = 256) -> Counter[int]:
    tokens = _tokens(text)
    features = tokens + ["".join(tokens[index : index + 2]) for index in range(len(tokens) - 1)]
    result: Counter[int] = Counter()
    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=4).digest()
        result[int.from_bytes(digest, "big") % dimensions] += 1
    return result


def _cosine(left: Counter[int], right: Counter[int]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0) for key, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


@dataclass(frozen=True)
class SecurityChunk:
    chunk_id: str
    document_id: str
    text: str
    title: str
    document_type: str
    parent_path: str = ""
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    document_id: str
    text: str
    score: float
    keyword_score: float
    vector_score: float
    citation: str
    document_type: str


class SecurityRAG:
    """Deterministic BM25 + hashed-vector retrieval and security reranking."""

    def search(
        self,
        query: str,
        chunks: Iterable[SecurityChunk],
        *,
        limit: int = 5,
        document_types: Sequence[str] | None = None,
    ) -> list[RetrievalResult]:
        candidates = [
            chunk for chunk in chunks
            if not document_types or chunk.document_type in set(document_types)
        ]
        if not candidates or not query.strip():
            return []
        query_tokens = _tokens(query)
        query_counts = Counter(query_tokens)
        documents = [Counter(_tokens(chunk.text + " " + chunk.title)) for chunk in candidates]
        average_length = sum(sum(doc.values()) for doc in documents) / max(1, len(documents))
        document_frequency = Counter(
            token for doc in documents for token in set(doc) if token in query_counts
        )
        query_vector = _vector(query)
        results = []
        for chunk, counts in zip(candidates, documents):
            length = max(1, sum(counts.values()))
            bm25 = 0.0
            for token in query_counts:
                frequency = counts.get(token, 0)
                if not frequency:
                    continue
                df = document_frequency[token]
                idf = math.log(1 + (len(candidates) - df + 0.5) / (df + 0.5))
                bm25 += idf * (frequency * 2.2) / (
                    frequency + 1.2 * (0.25 + 0.75 * length / max(1, average_length))
                )
            vector_score = _cosine(query_vector, _vector(chunk.text + " " + chunk.title))
            exact_bonus = 0.15 if query.casefold() in chunk.text.casefold() else 0.0
            policy_bonus = (
                0.08
                if any(term in query for term in ("制度", "规则", "条", "禁止", "允许"))
                and chunk.document_type == "security_policy"
                else 0.0
            )
            score = bm25 * 0.55 + vector_score * 0.37 + exact_bonus + policy_bonus
            citation = chunk.title + (f" > {chunk.parent_path}" if chunk.parent_path else "")
            results.append(
                RetrievalResult(
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.text,
                    round(score, 6),
                    round(bm25, 6),
                    round(vector_score, 6),
                    citation,
                    chunk.document_type,
                )
            )
        results.sort(key=lambda item: (-item.score, item.chunk_id))
        return results[: max(1, min(int(limit), 20))]

    def evaluate(
        self,
        cases: Iterable[Mapping[str, object]],
        chunks: Iterable[SecurityChunk],
        *,
        k: int = 5,
    ) -> dict[str, float | int]:
        chunk_values = tuple(chunks)
        case_values = tuple(cases)
        hits = 0
        reciprocal_rank = 0.0
        for case in case_values:
            relevant = {str(value) for value in case.get("relevant_chunk_ids", [])}
            results = self.search(str(case.get("query", "")), chunk_values, limit=k)
            ranks = [index for index, result in enumerate(results, start=1) if result.chunk_id in relevant]
            if ranks:
                hits += 1
                reciprocal_rank += 1 / min(ranks)
        count = len(case_values)
        return {
            "queries": count,
            "recall_at_k": round(hits / count, 4) if count else 0.0,
            "mrr": round(reciprocal_rank / count, 4) if count else 0.0,
        }


def chunk_security_document(
    document_id: str,
    title: str,
    document_type: str,
    text: str,
    *,
    max_chars: int = 1200,
) -> list[SecurityChunk]:
    """Section-aware chunks; headings become citation parent paths."""

    chunks: list[SecurityChunk] = []
    heading = ""
    buffer = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        is_heading = bool(re.match(r"^(#{1,6}\s+|第.{1,12}[章节条]|[一二三四五六七八九十]+[、.])", line))
        if is_heading:
            heading = line.lstrip("# ")[:200]
        if buffer and len(buffer) + len(line) + 1 > max_chars:
            ordinal = len(chunks)
            chunks.append(
                SecurityChunk(
                    f"{document_id}-c{ordinal}", document_id, buffer, title,
                    document_type, heading,
                )
            )
            buffer = line
        else:
            buffer = f"{buffer}\n{line}".strip()
    if buffer:
        ordinal = len(chunks)
        chunks.append(
            SecurityChunk(
                f"{document_id}-c{ordinal}", document_id, buffer, title,
                document_type, heading,
            )
        )
    return chunks


__all__ = [
    "RetrievalResult",
    "SecurityChunk",
    "SecurityRAG",
    "chunk_security_document",
]
