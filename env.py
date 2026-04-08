# env.py
import copy
from typing import Optional
from pydantic import BaseModel, Field
from typing import List, Dict, Literal
from database import get_fresh_database, CORRECT_TAGS, CORRECT_ANSWERS, DUPLICATE_PAIRS
from graders import grade_task_0, grade_task_1, grade_task_2
from hf_tools import find_similar_docs, classify_topic, generate_answer


# ── Models ──────────────────────────────────────────────────────

class Action(BaseModel):
    action_type: Literal[
        "SEARCH_DB", "TAG_QUESTION",
        "UPDATE_ANSWER", "MERGE_DUPLICATE", "DELETE_DOC", "SUBMIT_TASK"
    ]
    query: Optional[str] = None
    doc_id: Optional[str] = None
    tag: Optional[str] = None
    answer_text: Optional[str] = None
    duplicate_doc_id: Optional[str] = None


class DocumentPreview(BaseModel):
    doc_id: str
    question: str
    ideal_answer: Optional[str]
    tags: List[str]
    similarity_score: Optional[float] = None  # set when semantic search is used
    suggested_tag: Optional[str] = None        # set by HF classifier hint


class Observation(BaseModel):
    current_task_id: str
    current_task_description: str
    database_metrics: Dict[str, int]
    search_results: List[DocumentPreview]
    feedback: str
    step_count: int


class Reward(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    message: str


class StepResult(BaseModel):
    observation: Observation
    reward: float
    done: bool
    info: Dict = {}


# ── Environment ──────────────────────────────────────────────────

TASK_DESCRIPTIONS = {
    "task_0": (
        "EASY: The database was imported from 3 sources. 12 documents have wrong or missing tags. "
        "Fix them using tags: python, ml, sql, system-design. "
        "Bonus: delete junk rows (boilerplate scraped from page navigation). "
        "Doc IDs with issues include doc_003 through doc_024."
    ),
    "task_1": (
        "MEDIUM: 4 documents have empty ideal_answer fields (doc_005, doc_009, doc_013, doc_017, doc_020). "
        "Find them via SEARCH_DB and write a factually correct answer (>20 chars) for each. "
        "Also: doc_019 has a broken schema — its question field contains a category label, "
        "not a real question. Delete it."
    ),
    "task_2": (
        "HARD: The database has 4 near-duplicate pairs imported from different sources. "
        "Use SEARCH_DB with semantic queries to find them, then MERGE_DUPLICATE to remove "
        "the redundant copy. Pairs involve ml, python, sql, and system-design topics."
    ),
}


class RAGCuratorEnv:
    def __init__(self, task_id: str = "task_0"):
        self.task_id = task_id
        self.db = get_fresh_database()
        self.step_count = 0
        self.max_steps = 20
        self.last_search_results = []
        self.last_feedback = "Environment initialized. Ready to start."

    def _get_metrics(self) -> Dict[str, int]:
        total = len(self.db)
        untagged = sum(1 for d in self.db.values() if not d["tags"])
        missing_answers = sum(1 for d in self.db.values() if not d["ideal_answer"])
        return {
            "total_docs": total,
            "untagged_docs": untagged,
            "missing_answers": missing_answers,
        }

    def _build_observation(self) -> Observation:
        return Observation(
            current_task_id=self.task_id,
            current_task_description=TASK_DESCRIPTIONS[self.task_id],
            database_metrics=self._get_metrics(),
            search_results=self.last_search_results,
            feedback=self.last_feedback,
            step_count=self.step_count,
        )

    def reset(self) -> StepResult:
        self.db = get_fresh_database()
        self.step_count = 0
        self.last_search_results = []
        self.last_feedback = "Database reset. Start working on your task."
        return StepResult(
            observation=self._build_observation(),
            reward=0.5,  # Neutral reward (strictly between 0 and 1)
            done=False,
        )

    def state(self) -> dict:
        return {
            "task_id": self.task_id,
            "step_count": self.step_count,
            "db_snapshot": copy.deepcopy(self.db),
            "metrics": self._get_metrics(),
        }

    def _compute_progress_reward(self) -> float:
        """
        Compute current task progress as a reward signal.
        Returns a score in [0.0, 1.0] reflecting partial completion.
        """
        if self.task_id == "task_0":
            score, _ = grade_task_0(self.db)
        elif self.task_id == "task_1":
            score, _ = grade_task_1(self.db)
        else:
            score, _ = grade_task_2(self.db)
        return score

    def step(self, action: Action) -> StepResult:
        self.step_count += 1
        reward = 0.5  # Default neutral reward (strictly between 0 and 1)
        done = False

        # Track progress before action
        progress_before = self._compute_progress_reward()

        # ── SEARCH_DB ──
        if action.action_type == "SEARCH_DB":
            query = (action.query or "").lower()

            # Try semantic search first (HF API), fall back to keyword
            semantic_results = find_similar_docs(query, self.db, threshold=0.45)

            if semantic_results:
                results = [
                    DocumentPreview(
                        doc_id=r["doc_id"],
                        question=r["question"],
                        ideal_answer=r["ideal_answer"],
                        tags=r["tags"],
                        similarity_score=r["score"],
                    )
                    for r in semantic_results[:10]
                ]
            else:
                # Keyword fallback
                results = []
                for doc_id, doc in self.db.items():
                    if query in doc["question"].lower():
                        results.append(DocumentPreview(
                            doc_id=doc_id,
                            question=doc["question"],
                            ideal_answer=doc["ideal_answer"],
                            tags=doc["tags"],
                        ))
                results = results[:10]

            self.last_search_results = results
            self.last_feedback = f"Search returned {len(results)} results."
            reward = 0.5  # Search is neutral (strictly between 0 and 1)

        # ── TAG_QUESTION ──
        elif action.action_type == "TAG_QUESTION":
            if action.doc_id in self.db and action.tag:
                doc = self.db[action.doc_id]
                if action.tag not in doc["tags"]:
                    doc["tags"].append(action.tag)
                    expected = CORRECT_TAGS.get(action.doc_id, [])
                    if action.tag in expected:
                        self.last_feedback = f"Tagged {action.doc_id} with '{action.tag}'."
                    else:
                        # HF classifier hint on wrong tag
                        suggested = classify_topic(doc["question"])
                        hint = f" Suggested tag: '{suggested}'." if suggested else ""
                        self.last_feedback = f"Wrong tag '{action.tag}' for {action.doc_id}.{hint}"
                else:
                    self.last_feedback = f"Tag already exists on {action.doc_id}."
            else:
                self.last_feedback = "Invalid doc_id or missing tag."

        # ── UPDATE_ANSWER ──
        elif action.action_type == "UPDATE_ANSWER":
            if action.doc_id in self.db and action.answer_text:
                if len(action.answer_text.strip()) > 10:
                    self.db[action.doc_id]["ideal_answer"] = action.answer_text
                    self.last_feedback = f"Updated answer for {action.doc_id}."
                else:
                    # HF generation hint
                    question = self.db[action.doc_id]["question"]
                    suggested = generate_answer(question)
                    hint = f" Suggested: '{suggested[:80]}...'" if suggested else ""
                    self.last_feedback = f"Answer too short. Must be > 10 chars.{hint}"
            else:
                self.last_feedback = "Invalid doc_id or empty answer."

        # ── MERGE_DUPLICATE ──
        elif action.action_type == "MERGE_DUPLICATE":
            if action.doc_id in self.db and action.duplicate_doc_id in self.db:
                del self.db[action.duplicate_doc_id]
                self.last_feedback = f"Deleted duplicate {action.duplicate_doc_id}, kept {action.doc_id}."
            else:
                self.last_feedback = "One or both doc IDs not found."

        # ── DELETE_DOC ──
        elif action.action_type == "DELETE_DOC":
            from graders import JUNK_DOC_IDS, BROKEN_SCHEMA_IDS
            if action.doc_id in self.db:
                is_junk = action.doc_id in JUNK_DOC_IDS or action.doc_id in BROKEN_SCHEMA_IDS
                del self.db[action.doc_id]
                self.last_feedback = (
                    f"Deleted {action.doc_id}. {'Junk removed.' if is_junk else 'Warning: this may be a real document.'}"
                )
            else:
                self.last_feedback = f"doc_id '{action.doc_id}' not found."

        # ── SUBMIT_TASK ──
        elif action.action_type == "SUBMIT_TASK":
            if self.task_id == "task_0":
                score, msg = grade_task_0(self.db)
            elif self.task_id == "task_1":
                score, msg = grade_task_1(self.db)
            else:
                score, msg = grade_task_2(self.db)

            reward = score
            done = True
            self.last_feedback = f"TASK SUBMITTED. {msg} Final score: {score}"

        # Compute progress-based reward (delta from before action)
        if not done and action.action_type != "SEARCH_DB":
            progress_after = self._compute_progress_reward()
            delta = progress_after - progress_before  # Reward = improvement
            # Map delta to (0, 1) range: 0.5 = no change, >0.5 = improvement, <0.5 = regression
            reward = max(0.01, min(0.5 + delta, 0.99))

        # Step limit — auto-submit so agent always gets a graded score
        if self.step_count >= self.max_steps and not done:
            if self.task_id == "task_0":
                score, msg = grade_task_0(self.db)
            elif self.task_id == "task_1":
                score, msg = grade_task_1(self.db)
            else:
                score, msg = grade_task_2(self.db)
            reward = score
            done = True
            self.last_feedback += f" | Max steps reached. Auto-graded: {msg}"

        return StepResult(
            observation=self._build_observation(),
            reward=round(reward, 3),
            done=done,
        )