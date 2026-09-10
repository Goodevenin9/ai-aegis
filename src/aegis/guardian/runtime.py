"""Pure-Python inference for the bundled AI Aegis Guardian model.

The asset is loaded locally, SHA-256 verified, and never downloaded. Required
third-party attribution for the original algorithm and model remains in NOTICE.
"""

from __future__ import annotations

import base64
import binascii
import gzip
import hashlib
import hmac
import json
import math
import os
import re
import time
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

_TOKEN = re.compile(r"(?u)\b\w\w+\b")
_WS = re.compile(r"\s\s+")
_SPLIT = re.compile(r"(?<=[.!?])\s+|[\n\r]+|<!--|-->")
_B64 = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")
_HEX = re.compile(r"(?:[0-9a-fA-F]{2}){8,}")
_URL_ENC = re.compile(r"%[0-9A-Fa-f]{2}")

MAX_WINDOWS = 300
WORD_WINDOW = 24
WORD_STRIDE = 12
MAX_BLOBS = 20
MAX_DECODED = 4096
MAX_DEPTH = 3


def bundled_model_path() -> str:
    override = os.environ.get("AEGIS_GUARDIAN_RUNTIME", "").strip()
    return override or str(Path(__file__).with_name("model.runtime.json.gz"))


def _word_ngrams(text: str, lo: int, hi: int) -> list[str]:
    tokens = _TOKEN.findall(text.lower())
    output = list(tokens) if lo == 1 else []
    for size in range(max(lo, 2), hi + 1):
        output.extend(
            " ".join(tokens[index : index + size])
            for index in range(len(tokens) - size + 1)
        )
    return output


def _char_ngrams(text: str, lo: int, hi: int) -> list[str]:
    output: list[str] = []
    for word in _WS.sub(" ", text.lower()).split():
        padded = f" {word} "
        for size in range(lo, hi + 1):
            offset = 0
            output.append(padded[offset : offset + size])
            while offset + size < len(padded):
                offset += 1
                output.append(padded[offset : offset + size])
            if offset == 0:
                break
    return output


def _tfidf(
    ngrams: list[str], vocab: dict[str, int], idf: list[float], sublinear: bool
) -> dict[int, float]:
    counts = Counter(item for item in ngrams if item in vocab)
    vector = {
        vocab[term]: ((1.0 + math.log(count)) if sublinear else float(count))
        * idf[vocab[term]]
        for term, count in counts.items()
    }
    norm = math.sqrt(sum(value * value for value in vector.values()))
    return {key: value / norm for key, value in vector.items()} if norm else vector


class GuardianModel:
    """Local linear classifier loaded from the bundled model asset."""

    def __init__(self, bundle: dict) -> None:
        self.classes = bundle["classes"]
        self.benign = bundle["benign"]
        self.threshold = float(bundle["threshold"])
        self.window_min_score = float(bundle.get("window_min_score", 0.86))
        self.n_word = int(bundle["n_word_features"])
        self.word = bundle["word"]
        self.char = bundle["char"]
        self.coef = bundle["coef"]
        self.intercept = bundle["intercept"]

    @classmethod
    def load(cls, path: str) -> "GuardianModel":
        payload = Path(path).read_bytes()
        sidecar = Path(path + ".sha256")
        if sidecar.exists():
            expected = sidecar.read_text(encoding="utf-8").split()[0].strip()
            actual = hashlib.sha256(payload).hexdigest()
            if not hmac.compare_digest(expected, actual):
                raise ValueError("Guardian model integrity verification failed")
        if path.endswith(".gz"):
            payload = gzip.decompress(payload)
        return cls(json.loads(payload.decode("utf-8")))

    def predict(self, text: str) -> dict:
        word_vector = _tfidf(
            _word_ngrams(text, *self.word["ngram_range"]),
            self.word["vocab"], self.word["idf"], self.word["sublinear_tf"],
        )
        char_vector = _tfidf(
            _char_ngrams(text, *self.char["ngram_range"]),
            self.char["vocab"], self.char["idf"], self.char["sublinear_tf"],
        )
        scores = list(self.intercept)
        for class_index, row in enumerate(self.coef):
            scores[class_index] += sum(
                value * row[column] for column, value in word_vector.items()
            )
            scores[class_index] += sum(
                value * row[self.n_word + column]
                for column, value in char_vector.items()
            )
        highest = max(scores)
        exponents = [math.exp(score - highest) for score in scores]
        total = sum(exponents)
        ranked = sorted(
            zip(self.classes, (value / total for value in exponents)),
            key=lambda item: item[1], reverse=True,
        )
        malicious_score = sum(score for category, score in ranked if category != self.benign)
        verdict = "malicious" if malicious_score >= self.threshold else "benign"
        category = next((item[0] for item in ranked if item[0] != self.benign), None)
        return {
            "verdict": verdict,
            "category": category if verdict == "malicious" else None,
            "malicious_score": round(float(malicious_score), 4),
        }


def _looks_like_text(value: str) -> bool:
    return (
        len(value) >= 6
        and any(character.isalpha() for character in value)
        and sum(c.isprintable() or c.isspace() for c in value) / len(value) > 0.85
    )


def _decode_into(text: str, depth: int, budget: list[int], output: list[str]) -> None:
    if depth >= MAX_DEPTH or budget[0] <= 0:
        return
    for pattern, encoding in ((_B64, "base64"), (_HEX, "hex")):
        for match in pattern.finditer(text):
            if budget[0] <= 0:
                return
            blob = match.group(0)
            try:
                raw = (
                    base64.b64decode(blob + "=" * (-len(blob) % 4), validate=False)
                    if encoding == "base64"
                    else bytes.fromhex(blob[: len(blob) - (len(blob) % 2)])
                )[:MAX_DECODED]
                decoded = raw.decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError):
                continue
            if _looks_like_text(decoded):
                budget[0] -= 1
                output.append(decoded)
                _decode_into(decoded, depth + 1, budget, output)


def _extra_spans(text: str) -> list[str]:
    output: list[str] = []
    budget = [MAX_BLOBS]
    if _URL_ENC.search(text):
        decoded = unquote(text)
        if decoded != text and _looks_like_text(decoded):
            budget[0] -= 1
            output.append(decoded)
            _decode_into(decoded, 0, budget, output)
    _decode_into(text, 0, budget, output)
    if len(text.split()) > WORD_WINDOW or "\n" in text:
        for segment in _SPLIT.split(text):
            words = segment.strip().split()
            if not words:
                continue
            if len(words) <= WORD_WINDOW:
                output.append(" ".join(words))
            else:
                for index in range(0, len(words), WORD_STRIDE):
                    output.append(" ".join(words[index : index + WORD_WINDOW]))
                    if len(output) >= MAX_WINDOWS:
                        break
            if len(output) >= MAX_WINDOWS:
                break
    elif len(text) <= 400:
        output.append(text[::-1])
    return output[:MAX_WINDOWS]


def _predict_windowed(model: GuardianModel, text: str) -> dict:
    best = model.predict(text)
    threshold = max(model.threshold, model.window_min_score)
    for span in _extra_spans(text):
        candidate = model.predict(span)
        if (
            candidate["malicious_score"] >= threshold
            and candidate["malicious_score"] > best["malicious_score"]
        ):
            best = {**candidate, "verdict": "malicious"}
    return best


def analyze(text: str, model: GuardianModel, *, direction: str = "outgoing") -> dict:
    del direction
    started = time.perf_counter()
    prediction = _predict_windowed(model, text)
    is_threat = prediction["verdict"] == "malicious"
    risk_score = max(0, min(100, round(prediction["malicious_score"] * 100)))
    confidence = prediction["malicious_score"] if is_threat else 1 - prediction["malicious_score"]
    matched_rules = []
    if is_threat:
        severity = (
            "critical" if risk_score >= 90 else "high" if risk_score >= 75
            else "medium" if risk_score >= 50 else "low"
        )
        matched_rules.append({
            "rule_id": "aegis_guardian_model",
            "rule_name": "AI Aegis Guardian (ML)",
            "category": prediction["category"],
            "severity": severity,
            "source": "model",
            "matched_patterns": [],
            "confidence": round(float(prediction["malicious_score"]), 4),
            "mitre_techniques": [],
        })
    return {
        "is_threat": is_threat,
        "threat_type": prediction["category"] if is_threat else None,
        "risk_score": risk_score,
        "confidence": round(max(0.0, min(1.0, confidence)), 4),
        "matched_rules": matched_rules,
        "analysis_id": None,
        "processing_time_ms": int((time.perf_counter() - started) * 1000),
        "request_id": None,
        "analysis_source": "model",
        "llm_review": None,
        "redacted_text": None,
        "action_taken": "logged",
    }
