"""
hf_tools.py — HuggingFace Inference API helpers (no local model loading).

All calls are pure HTTP via httpx. Requires HF_TOKEN env var.
Falls back gracefully if the API is unavailable (rate limit / cold start).
"""
import os
import httpx

HF_TOKEN: str = os.environ.get("HF_TOKEN", "")
HF_API: str   = "https://api-inference.huggingface.co/models"

HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}
TIMEOUT = 20  # seconds — HF cold starts can be slow


# ── Semantic Similarity ────────────────────────────────────────────────────────
# Used by: SEARCH_DB (task_2 duplicate detection)
# Model: sentence-transformers/all-MiniLM-L6-v2 (free, fast, 80MB)

def semantic_similarity(text1: str, text2: str) -> float:
    """
    Returns cosine similarity [0.0, 1.0] between two strings.
    Falls back to 0.0 on any error.
    """
    if not HF_TOKEN:
        return 0.0
    try:
        r = httpx.post(
            f"{HF_API}/sentence-transformers/all-MiniLM-L6-v2",
            headers=HEADERS,
            json={"inputs": {"source_sentence": text1, "sentences": [text2]}},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        result = r.json()
        # API returns a list of scores
        if isinstance(result, list) and len(result) > 0:
            return float(result[0])
        return 0.0
    except Exception:
        return 0.0


def find_similar_docs(query: str, db: dict, threshold: float = 0.75) -> list[dict]:
    """
    Returns docs from db with semantic similarity >= threshold to query.
    Sorted by similarity descending.
    """
    scored = []
    for doc_id, doc in db.items():
        score = semantic_similarity(query, doc["question"])
        if score >= threshold:
            scored.append({"doc_id": doc_id, "score": round(score, 3), **doc})
    return sorted(scored, key=lambda x: x["score"], reverse=True)


# ── Zero-Shot Classification ───────────────────────────────────────────────────
# Used by: TAG_QUESTION hint / agent tool (task_0)
# Model: facebook/bart-large-mnli (free, no fine-tuning needed)

TOPIC_LABELS = ["python", "ml", "sql", "system-design"]

def classify_topic(question: str) -> str:
    """
    Returns the most likely topic tag for a question.
    Falls back to empty string on error.
    """
    if not HF_TOKEN:
        return ""
    try:
        r = httpx.post(
            f"{HF_API}/facebook/bart-large-mnli",
            headers=HEADERS,
            json={
                "inputs": question,
                "parameters": {"candidate_labels": TOPIC_LABELS},
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        result = r.json()
        if "labels" in result:
            return result["labels"][0]  # highest scoring label
        return ""
    except Exception:
        return ""


# ── Answer Generation ──────────────────────────────────────────────────────────
# Used by: UPDATE_ANSWER hint (task_1)
# Model: microsoft/Phi-3-mini-4k-instruct (free, fast, instruction-tuned)

def generate_answer(question: str) -> str:
    """
    Generates a concise factual answer for a technical question.
    Falls back to empty string on error.
    """
    if not HF_TOKEN:
        return ""
    prompt = (
        f"<|user|>\nAnswer this technical interview question in 1-2 sentences:\n"
        f"{question}\n<|end|>\n<|assistant|>\n"
    )
    try:
        r = httpx.post(
            f"{HF_API}/microsoft/Phi-3-mini-4k-instruct",
            headers=HEADERS,
            json={
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 120,
                    "temperature": 0.1,
                    "return_full_text": False,
                },
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        result = r.json()
        if isinstance(result, list) and result:
            return result[0].get("generated_text", "").strip()
        return ""
    except Exception:
        return ""
