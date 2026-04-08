"""
server.py — FastAPI OpenEnv server for RAG DB Curator

Exposes: GET /health, POST /reset/{task_id}, POST /step/{task_id}, GET /state/{task_id}
"""
from fastapi import FastAPI, HTTPException
from env import RAGCuratorEnv, Action, StepResult
from typing import Dict

app = FastAPI(
    title="RAG DB Curator — OpenEnv",
    description=(
        "An AI Data Engineer environment for cleaning, tagging, and "
        "deduplicating a messy RAG Knowledge Base."
    ),
    version="0.1.0",
)

# One env instance per task_id (reset creates a fresh one)
envs: Dict[str, RAGCuratorEnv] = {}

VALID_TASKS = {"task_0", "task_1", "task_2"}


# ── Health / root ──────────────────────────────────────────────────────────────

@app.get("/")
@app.get("/health")
def health():
    """Used by the pre-validation script to verify the Space is alive."""
    return {"status": "ok", "env": "rag-db-curator", "version": "0.1.0"}


# ── OpenEnv core endpoints ─────────────────────────────────────────────────────

@app.post("/reset", response_model=StepResult)
@app.post("/reset/{task_id}", response_model=StepResult)
def reset(task_id: str = "task_0"):
    """Start a fresh episode. Creates or replaces the env for this task_id."""
    if task_id not in VALID_TASKS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown task_id '{task_id}'. Valid: {sorted(VALID_TASKS)}"
        )
    envs[task_id] = RAGCuratorEnv(task_id=task_id)
    return envs[task_id].reset()


@app.post("/step/{task_id}", response_model=StepResult)
def step(task_id: str, action: Action):
    """Execute one action in the environment."""
    if task_id not in VALID_TASKS:
        raise HTTPException(status_code=404, detail=f"Unknown task_id '{task_id}'.")
    if task_id not in envs:
        # Auto-init so agents don't have to call reset first
        envs[task_id] = RAGCuratorEnv(task_id=task_id)
        envs[task_id].reset()
    return envs[task_id].step(action)


@app.get("/state/{task_id}")
def state(task_id: str):
    """Inspect the current state without consuming a step."""
    if task_id not in envs:
        raise HTTPException(
            status_code=404,
            detail=f"No active session for '{task_id}'. Call /reset/{task_id} first.",
        )
    return envs[task_id].state()


# ── List available tasks ───────────────────────────────────────────────────────

@app.get("/tasks")
def list_tasks():
    return {
        "tasks": [
            {"id": "task_0", "difficulty": "easy",   "name": "Tag Untagged Questions"},
            {"id": "task_1", "difficulty": "medium",  "name": "Fill Missing Answers"},
            {"id": "task_2", "difficulty": "hard",    "name": "Semantic Deduplication"},
        ]
    }


# ── Entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
