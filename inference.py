"""
inference.py — Baseline inference script for RAG DB Curator OpenEnv

Follows the strict [START] / [STEP] / [END] log format required by the hackathon.

Usage with HuggingFace Inference API:
    export HF_TOKEN="hf_..."
    export MODEL_NAME="meta-llama/Llama-3.2-3B-Instruct"
    export ENV_BASE_URL="https://s777k-openenv-rag-curator.hf.space"
    python inference.py

Usage with OpenAI API:
    export API_BASE_URL="https://api.openai.com/v1"
    export MODEL_NAME="gpt-4o-mini"
    export OPENAI_API_KEY="sk-..."
    export ENV_BASE_URL="https://s777k-openenv-rag-curator.hf.space"
    python inference.py
"""
import json
import os
import time
from typing import Any, Dict, List, Optional

import httpx
from openai import OpenAI

# ── Configuration (from environment variables) ─────────────────────────────────
API_BASE_URL: str = os.environ.get("API_BASE_URL", "")
MODEL_NAME: str   = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.2-3B-Instruct")
HF_TOKEN: str     = os.environ.get("HF_TOKEN", "")
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

# Determine which API to use
USE_HF_INFERENCE = not API_BASE_URL and HF_TOKEN
API_KEY: str = HF_TOKEN if USE_HF_INFERENCE else OPENAI_API_KEY

if USE_HF_INFERENCE:
    API_BASE_URL = "https://api-inference.huggingface.co/models"
    print(f"[INFO] Using HuggingFace Inference API with model: {MODEL_NAME}", flush=True)
    print(f"[INFO] Note: Trying new router endpoint if old API fails", flush=True)
elif not API_BASE_URL:
    API_BASE_URL = "https://api.openai.com/v1"
    print(f"[INFO] Using OpenAI API with model: {MODEL_NAME}", flush=True)
else:
    print(f"[INFO] Using custom API: {API_BASE_URL} with model: {MODEL_NAME}", flush=True)

# ── Environment URL (local or HF Space) ────────────────────────────────────────
ENV_BASE_URL: str = os.environ.get("ENV_BASE_URL", "http://localhost:7860")

# ── Episode settings ────────────────────────────────────────────────────────────
MAX_STEPS: int       = 15
TEMPERATURE: float   = 0.0
MAX_TOKENS: int      = 512
TASK_IDS: List[str]  = ["task_0", "task_1", "task_2"]

# ── Scoring ─────────────────────────────────────────────────────────────────────
SUCCESS_SCORE_THRESHOLD: float = 0.5
BENCHMARK: str = "rag-db-curator"


# ══════════════════════════════════════════════════════════════════════════════
#  Structured log helpers  (MANDATORY FORMAT — do not change field names)
# ══════════════════════════════════════════════════════════════════════════════

def log_start(*, task: str, env: str, model: str) -> None:
    """Emit the [START] log line."""
    payload = {"task": task, "env": env, "model": model}
    print(f"[START] {json.dumps(payload)}", flush=True)


def log_step(*,
    step:   int,
    action: Any,
    reward: float,
    done:   bool,
    error:  Optional[str],
) -> None:
    """Emit one [STEP] log line."""
    payload = {
        "step":   step,
        "action": action if isinstance(action, (str, dict)) else str(action),
        "reward": round(float(reward), 4),
        "done":   done,
        "error":  error,
    }
    print(f"[STEP] {json.dumps(payload)}", flush=True)


def log_end(*,
    success: bool,
    steps:   int,
    score:   float,
    rewards: List[float],
) -> None:
    """Emit the [END] log line."""
    payload = {
        "success": success,
        "steps":   steps,
        "score":   round(float(score), 4),
        "rewards": [round(float(r), 4) for r in rewards],
    }
    print(f"[END] {json.dumps(payload)}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
#  Environment HTTP client
# ══════════════════════════════════════════════════════════════════════════════

class RAGCuratorClient:
    """Thin HTTP wrapper around the FastAPI OpenEnv server."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(timeout=30)

    def reset(self, task_id: str) -> Dict:
        r = self._http.post(f"{self.base_url}/reset/{task_id}")
        r.raise_for_status()
        return r.json()

    def step(self, task_id: str, action: Dict) -> Dict:
        r = self._http.post(
            f"{self.base_url}/step/{task_id}",
            json=action,
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()

    def state(self, task_id: str) -> Dict:
        r = self._http.get(f"{self.base_url}/state/{task_id}")
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._http.close()


# ══════════════════════════════════════════════════════════════════════════════
#  LLM helpers
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are an expert AI Data Engineer working inside a RAG Vector Database
Curator environment. Your job is to clean a messy interview Q&A knowledge base.

You can issue exactly ONE action per turn. Respond with ONLY a valid JSON object
matching one of the schemas below — no markdown fences, no explanation.

Available actions:
{"action_type": "SEARCH_DB", "query": "<keyword>"}
{"action_type": "TAG_QUESTION", "doc_id": "<id>", "tag": "<python|ml|sql|system-design>"}
{"action_type": "UPDATE_ANSWER", "doc_id": "<id>", "answer_text": "<full answer>"}
{"action_type": "MERGE_DUPLICATE", "doc_id": "<keep_id>", "duplicate_doc_id": "<delete_id>"}
{"action_type": "DELETE_DOC", "doc_id": "<id>"}
{"action_type": "SUBMIT_TASK"}

Rules:
- For task_0 (Tagging): Search separately for "python", "ml", "sql", "system-design", "docker", "api"
  to find ALL docs with wrong/missing tags. Valid tags: python, ml, sql, system-design.
  Also delete junk rows (doc_025, doc_026, doc_027) — they are page boilerplate, not real questions.
- For task_1 (Fill Answers): Search for docs with empty ideal_answer, then UPDATE_ANSWER.
  Also delete doc_019 — it has a broken schema (question field = category label).
- For task_2 (Deduplication): Search semantically for similar questions, then MERGE_DUPLICATE.
- When you believe you have completed the task, emit {"action_type": "SUBMIT_TASK"}.
- Never emit anything other than the raw JSON action object."""


def build_user_message(step: int, obs: Dict, last_reward: float, history: List[str]) -> str:
    obs_data    = obs.get("observation", obs)
    metrics     = obs_data.get("database_metrics", {})
    feedback    = obs_data.get("feedback", "")
    task_desc   = obs_data.get("current_task_description", "")
    search_hits = obs_data.get("search_results", [])

    search_summary = ""
    if search_hits:
        lines = []
        for hit in search_hits:
            lines.append(
                f"  - {hit['doc_id']}: \"{hit['question']}\" "
                f"| answer={'<empty>' if not hit.get('ideal_answer') else hit['ideal_answer'][:60]} "
                f"| tags={hit.get('tags', [])}"
            )
        search_summary = "Search results:\n" + "\n".join(lines)

    recent_history = "\n".join(history[-4:]) if history else "None"

    return f"""Step {step} | Last reward: {last_reward:+.3f}
Task: {task_desc}
DB Metrics: {json.dumps(metrics)}
Feedback: {feedback}
{search_summary}
Recent actions:
{recent_history}

What is your next action? Respond with ONLY the JSON action object."""


def get_model_action(client: OpenAI, step: int, obs: Dict, last_reward: float, history: List[str]) -> Dict:
    """Call the LLM and parse its JSON response. Falls back to SUBMIT_TASK on any failure."""
    user_msg = build_user_message(step, obs, last_reward, history)
    try:
        if USE_HF_INFERENCE:
            # Use HuggingFace Inference API directly with text-generation endpoint
            import httpx
            
            # Try multiple model endpoints with new HF router
            models_to_try = [
                MODEL_NAME,
                "Qwen/Qwen2.5-Coder-3B-Instruct",
                "Qwen/Qwen2.5-3B-Instruct", 
                "mistralai/Mistral-7B-Instruct-v0.2",
                "HuggingFaceH4/zephyr-7b-beta",
                "tiiuae/falcon-7b-instruct",
                "bigscience/bloom-7b1",
            ]
            
            text = None
            last_error = None
            
            for model in models_to_try:
                try:
                    print(f"[DEBUG] Trying model: {model}", flush=True)
                    
                    # Try new router endpoint first
                    try:
                        response = httpx.post(
                            f"https://api-inference.huggingface.co/models/{model}",
                            headers={"Authorization": f"Bearer {API_KEY}"},
                            json={
                                "inputs": f"{SYSTEM_PROMPT}\n\n{user_msg}",
                                "parameters": {
                                    "max_new_tokens": MAX_TOKENS,
                                    "temperature": TEMPERATURE,
                                    "return_full_text": False,
                                }
                            },
                            timeout=30,
                        )
                        response.raise_for_status()
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 410:
                            # Try new router endpoint
                            print(f"[DEBUG]   Old API deprecated, trying router...", flush=True)
                            response = httpx.post(
                                f"https://router.huggingface.co/models/{model}",
                                headers={"Authorization": f"Bearer {API_KEY}"},
                                json={
                                    "inputs": f"{SYSTEM_PROMPT}\n\n{user_msg}",
                                    "parameters": {
                                        "max_new_tokens": MAX_TOKENS,
                                        "temperature": TEMPERATURE,
                                        "return_full_text": False,
                                    }
                                },
                                timeout=30,
                            )
                            response.raise_for_status()
                        else:
                            raise
                    
                    result = response.json()
                    
                    if isinstance(result, list) and len(result) > 0:
                        text = result[0].get("generated_text", "").strip()
                    elif isinstance(result, dict) and "generated_text" in result:
                        text = result["generated_text"].strip()
                    else:
                        continue
                    
                    if text:
                        print(f"[DEBUG] Successfully used model: {model}", flush=True)
                        break
                except Exception as e:
                    last_error = e
                    continue
            
            if not text:
                raise Exception(f"All models failed. Last error: {last_error}")
        else:
            # Use OpenAI-compatible API
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                stream=False,
            )
            text = (completion.choices[0].message.content or "").strip()
        
        # Strip accidental markdown fences
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        action = json.loads(text)
        if "action_type" not in action:
            raise ValueError("Missing action_type")
        return action
    except Exception as exc:
        print(f"[DEBUG] LLM parse error at step {step}: {exc}", flush=True)
        return {"action_type": "SUBMIT_TASK"}


# ══════════════════════════════════════════════════════════════════════════════
#  Run one episode for a given task
# ══════════════════════════════════════════════════════════════════════════════

def run_episode(client: OpenAI, env: RAGCuratorClient, task_id: str) -> float:
    """Runs a full episode for one task. Returns the final normalised score."""
    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    rewards:     List[float] = []
    history:     List[str]   = []
    steps_taken: int         = 0
    score:       float       = 0.0
    success:     bool        = False

    result      = env.reset(task_id)
    last_reward = 0.0

    try:
        for step in range(1, MAX_STEPS + 1):
            if result.get("done", False):
                break

            action = get_model_action(client, step, result, last_reward, history)

            error_msg: Optional[str] = None
            try:
                result = env.step(task_id, action)
            except Exception as exc:
                error_msg = str(exc)
                print(f"[DEBUG] env.step error: {exc}", flush=True)
                result = {"done": True, "reward": 0.0, "observation": {}}

            reward      = float(result.get("reward", 0.0))
            done        = result.get("done", False)
            last_reward = reward
            rewards.append(reward)
            steps_taken = step

            log_step(step=step, action=action, reward=reward, done=done, error=error_msg)
            history.append(f"Step {step}: {action.get('action_type')} → reward {reward:+.3f}")

            if done:
                score = reward
                break

        if not rewards:
            score = 0.0
        elif score == 0.0:
            score = rewards[-1]

        score   = min(max(score, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


# ══════════════════════════════════════════════════════════════════════════════
#  Main entry point
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    env    = RAGCuratorClient(base_url=ENV_BASE_URL)

    print(f"[INFO] Model:   {MODEL_NAME}", flush=True)
    print(f"[INFO] API URL: {API_BASE_URL}", flush=True)
    print(f"[INFO] Env URL: {ENV_BASE_URL}", flush=True)
    print(f"[INFO] Tasks:   {TASK_IDS}", flush=True)
    print("", flush=True)

    all_scores: Dict[str, float] = {}
    try:
        for task_id in TASK_IDS:
            print(f"{'='*60}", flush=True)
            print(f"[INFO] Starting episode for {task_id}", flush=True)
            print(f"{'='*60}", flush=True)
            t0    = time.time()
            score = run_episode(client, env, task_id)
            elapsed = time.time() - t0
            all_scores[task_id] = score
            print(f"[INFO] {task_id} finished | score={score:.4f} | elapsed={elapsed:.1f}s", flush=True)
            print("", flush=True)
    finally:
        env.close()

    print("=" * 60, flush=True)
    print("FINAL SCORES", flush=True)
    print("=" * 60, flush=True)
    for task_id, score in all_scores.items():
        status = "✓ PASS" if score >= SUCCESS_SCORE_THRESHOLD else "✗ FAIL"
        print(f"  {task_id:<12} {score:.4f}   {status}", flush=True)
    avg = sum(all_scores.values()) / len(all_scores) if all_scores else 0.0
    print(f"  {'AVERAGE':<12} {avg:.4f}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
