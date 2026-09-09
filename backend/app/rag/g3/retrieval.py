"""Offline exact/alias/code routing plus BM25; internal IDs never become display labels."""

import math
import unicodedata
from collections import Counter
from time import perf_counter

from app.rag.g3.validator import SECTIONS, require, scan
from app.rag.retrieval import normalize

INTENTS = {
    "required_documents": ("ho so", "giay to", "documents"),
    "fees": ("le phi", "phi", "bao nhieu tien", "fees"),
    "processing_times": ("thoi gian", "bao lau", "may ngay", "thoi han"),
    "receiving_authority": ("nop o dau", "noi nop", "noi tiep nhan", "co quan tiep nhan"),
    "submission_methods": ("hinh thuc", "truc tuyen", "online", "nop cach nao"),
    "steps": ("trinh tu", "cac buoc"),
    "legal_bases": ("can cu phap ly",),
    "applicant_scope": ("doi tuong", "ai duoc"),
}


def bm25(query, texts):
    docs = [Counter(normalize(text).split()) for text in texts]
    if not docs:
        return []
    avg = sum(sum(d.values()) for d in docs) / len(docs) or 1
    terms = set(normalize(query).split())
    df = {t: sum(t in d for d in docs) for t in terms}
    scores = []
    for doc in docs:
        score = 0.0
        for t in terms:
            tf = doc[t]
            if tf:
                idf = math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5))
                score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * sum(doc.values()) / avg))
        scores.append(score)
    return scores


def retrieve(data, query, top_k=5, procedure_id=None, category=None, as_of=None):
    require(isinstance(query, str) and 0 < len(query.strip()) <= 4000, "INVALID_QUERY")
    require(type(top_k) is int and 1 <= top_k <= 8, "INVALID_TOP_K")
    # User input need not already satisfy the producer's NFC/trim invariant.
    # Normalize a copy before the PII tripwire and lexical retrieval.
    normalized_query = unicodedata.normalize("NFC", query.strip())
    scan(normalized_query)
    q = " " + normalize(normalized_query) + " "
    fields = {
        field
        for field, phrases in INTENTS.items()
        if any(" " + term + " " in q for term in phrases)
    }
    result = {
        "status": "INSUFFICIENT_DATA",
        "procedure_id": None,
        "evidence": [],
        "missing_fields": [],
        "reason": "RETRIEVAL_MISS",
    }
    pool = [
        p
        for p in data.procedures.values()
        if (procedure_id is None or p["procedure_id"] == procedure_id)
        and (category is None or p["category_code"] == category)
    ]
    exact = []
    for p in pool:
        names = [p["title"], *p["aliases"]]
        names += [data.sources[s]["procedure_code"] for s in p["source_ids"]]
        if any(name and " " + normalize(name) + " " in q for name in names):
            exact.append(p)
    # Routing includes rejected procedures so an explicit pending title cannot
    # accidentally fall through to a different approved procedure.
    if exact:
        pool = exact
    elif not procedure_id:
        scores = bm25(
            normalized_query,
            [" ".join([p["title"], *p["aliases"], p["category_label"]]) for p in pool],
        )
        pool = [p for p, score in zip(pool, scores) if score > 0]
    if len(pool) > 1:
        return dict(result, status="NEED_CLARIFICATION", reason="AMBIGUOUS_PROCEDURE")
    if not pool:
        return result
    p = pool[0]
    pid = p["procedure_id"]
    result["procedure_id"] = pid
    if pid not in data.accepted:
        return dict(result, reason=data.rejected[pid])
    missing = sorted(fields & set(p["missing_fields"]))
    if missing:
        return dict(result, missing_fields=missing, reason="DATA_MISSING")
    # No fragment from a declared missing field may enter any evidence bundle.
    allowed = {
        fid
        for field, refs in p["field_evidence"].items()
        if field not in p["missing_fields"] and (not fields or field in fields)
        for fid in refs
    }
    frags = [
        f
        for f in data.fragments.values()
        if f["procedure_id"] == pid and f["fragment_id"] in allowed
    ]
    if as_of:
        from datetime import date

        try:
            date.fromisoformat(as_of)
        except (TypeError, ValueError):
            require(False, "INVALID_AS_OF")
    usable = []
    for f in frags:
        s = data.sources[f["source_id"]]
        if s["validity_status"] in {"EXPIRED", "FUTURE"}:
            continue
        if as_of and (
            s["validity_status"] != "CURRENT"
            or not s["effective_from"]
            or as_of < s["effective_from"]
            or (s["effective_to"] and as_of > s["effective_to"])
        ):
            continue
        usable.append(f)
    scores = bm25(normalized_query, [f["text"] for f in usable])
    ranked = sorted(zip(scores, usable), key=lambda x: (-x[0], x[1]["fragment_id"]))
    selected, budget = [], 0
    for score, f in ranked[:top_k]:
        if budget + len(f["text"]) > 32000:
            break
        budget += len(f["text"])
        s = data.sources[f["source_id"]]
        selected.append(
            {
                "fragment_id": f["fragment_id"],
                "source_id": f["source_id"],
                "procedure_id": pid,
                "section_type": f["section_type"],
                "title": p["title"],
                "text": f["text"],
                "url": s["public_url"],
                "source_type": s["source_type"],
                "score": round(score, 10),
            }
        )
    covered = {f["section_type"] for f in selected}
    if fields and not {SECTIONS[field] for field in fields} <= covered:
        return dict(result, reason="RETRIEVAL_MISS")
    return dict(
        result,
        status="ANSWER" if selected else "INSUFFICIENT_DATA",
        evidence=selected,
        reason=None if selected else "DATA_MISSING",
    )


def evaluate(data, split="DEV", top_k=5):
    results = []
    for q in data.groups[4].values():
        if q["split"] != split:
            continue
        started = perf_counter()
        found = retrieve(data, q["question"], top_k)
        latency = (perf_counter() - started) * 1000
        ids = {e["fragment_id"] for e in found["evidence"]}
        expected = set(q["gold_fragment_ids"])
        recall = len(ids & expected) / len(expected) if expected else None
        routing = found["procedure_id"] == q["procedure_id"] if q["procedure_id"] else None
        status = found["status"] == q["expected_status"]
        error = (
            "ROUTING_ERROR"
            if routing is False
            else "RETRIEVAL_MISS"
            if recall is not None and recall < 1
            else "DATA_MISSING"
            if not status
            else None
        )
        results.append(
            {
                "question_id": q["question_id"],
                "routing_correct": routing,
                "status_correct": status,
                "recall_at_k": recall,
                "retrieved_ids": sorted(ids),
                "error": error,
                "pass": error is None,
                "latency_ms": round(latency, 4),
            }
        )
    require(bool(results), "EMPTY_EVALUATION_SPLIT")
    recalls = [r["recall_at_k"] for r in results if r["recall_at_k"] is not None]
    routing = [r["routing_correct"] for r in results if r["routing_correct"] is not None]
    times = sorted(r["latency_ms"] for r in results)
    return {
        "dataset_version": data.version,
        "corpus_sha256": data.fingerprint,
        "split": split,
        "top_k": top_k,
        "query_count": len(results),
        "scope": "offline retrieval only; no generation or legal-quality assessment",
        "routing_accuracy": sum(routing) / len(routing) if routing else None,
        "recall_at_k": sum(recalls) / len(recalls) if recalls else None,
        "p95_ms": times[math.ceil(0.95 * len(times)) - 1],
        "results": results,
    }
