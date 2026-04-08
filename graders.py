"""
graders.py — Deterministic task graders for the RAG Curator environment.

All graders return (score: float, message: str) where score is in [0.0, 1.0].
"""
from database import CORRECT_TAGS, CORRECT_ANSWERS, DUPLICATE_PAIRS

# Junk doc IDs — boilerplate scraped from page navigation
JUNK_DOC_IDS = {"doc_025", "doc_026", "doc_027"}

# Broken schema doc IDs — source_c rows where question/answer fields are swapped
BROKEN_SCHEMA_IDS = {"doc_019"}


def grade_task_0(db: dict) -> tuple[float, str]:
    """
    Easy: Fix wrong/missing tags on 12 documents.
    Also awards bonus points for deleting junk/broken-schema rows.
    Score = (correctly_tagged + junk_removed_bonus) normalised to [0, 1].
    """
    tag_correct = 0
    tag_total = len(CORRECT_TAGS)

    for doc_id, expected_tags in CORRECT_TAGS.items():
        if doc_id not in db:
            continue
        actual = db[doc_id].get("tags", [])
        if any(t in actual for t in expected_tags):
            tag_correct += 1

    # Bonus: junk rows removed (up to 0.2 extra, normalised)
    junk_removed = sum(1 for jid in JUNK_DOC_IDS if jid not in db)
    junk_bonus = round(junk_removed / len(JUNK_DOC_IDS) * 0.2, 2)

    base_score = round(tag_correct / tag_total, 2)
    score = min(round(base_score + junk_bonus, 2), 1.0)
    message = (
        f"{tag_correct}/{tag_total} docs correctly tagged. "
        f"Junk removed: {junk_removed}/{len(JUNK_DOC_IDS)}."
    )
    return score, message


def grade_task_1(db: dict) -> tuple[float, str]:
    """
    Medium: Fill 4 empty ideal_answer fields.
    Score = filled / total. Answer must be > 20 chars to count.
    Penalty for broken-schema rows still present (doc_019 has swapped fields).
    """
    filled = 0
    total = len(CORRECT_ANSWERS)

    for doc_id in CORRECT_ANSWERS:
        if doc_id not in db:
            continue
        answer = db[doc_id].get("ideal_answer", "")
        if answer and len(answer.strip()) > 20:
            filled += 1

    # Penalty: broken schema row still present
    broken_penalty = 0.1 if "doc_019" in db else 0.0

    score = max(round(filled / total - broken_penalty, 2), 0.0)
    message = (
        f"{filled}/{total} missing answers filled. "
        f"Broken schema penalty: {broken_penalty}."
    )
    return score, message


def grade_task_2(db: dict) -> tuple[float, str]:
    """
    Hard: Resolve 4 near-duplicate pairs.
    Perfect: keep one, delete the other → 1.0 per pair.
    Partial: both deleted → 0.5 per pair (lost unique content).
    Miss: both still present → 0.0 per pair.
    """
    resolved = 0.0
    total = len(DUPLICATE_PAIRS)

    for keep_id, delete_id in DUPLICATE_PAIRS:
        keep_exists   = keep_id   in db
        delete_exists = delete_id in db

        if keep_exists and not delete_exists:
            resolved += 1.0       # perfect
        elif not keep_exists and not delete_exists:
            resolved += 0.5       # partial — both gone
        # else both exist → 0

    score = round(resolved / total, 2)
    message = f"{resolved}/{total} duplicate pairs resolved."
    return score, message
