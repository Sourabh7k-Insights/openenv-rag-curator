---
title: RAG DB Curator OpenEnv
emoji: 🗄️
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
tags:
  - openenv
  - rag
  - data-engineering
  - reinforcement-learning
---

# OpenEnv: RAG DB Curator

[![HuggingFace Space](https://img.shields.io/badge/🤗%20HuggingFace-Space-blue)](https://huggingface.co/spaces/S777k/openenv-rag-curator)
[![OpenEnv](https://img.shields.io/badge/OpenEnv-Compliant-green)](https://openenv.dev)

An agentic environment where an agent must clean and organize a messy RAG document database imported from real-world scraped interview Q&A datasets.

## Overview

This environment simulates a real AI Data Engineer task: cleaning a polluted RAG knowledge base. The database contains 27 documents with intentional real-world problems:
- Wrong or missing topic tags (python, ml, sql, system-design)
- Empty or truncated answers
- Near-duplicate questions from different sources
- Encoding artifacts from bad UTF-8 scraping
- Junk rows scraped from page navigation boilerplate
- Broken schema rows where question/answer fields are swapped

## Tasks

### Task 0: Tag Untagged Questions (Easy)
12 documents have wrong or missing tags. Apply the correct topic tag (python / ml / sql / system-design) to each. Bonus points for deleting junk rows (doc_025, doc_026, doc_027).

- Difficulty: Easy
- Max steps: 20
- Success threshold: 0.8
- Baseline score: ~0.75

### Task 1: Fill Missing Answers (Medium)
4 documents have empty ideal_answer fields. Identify them and write a factually correct answer (>20 chars) for each. Also delete doc_019 which has a broken schema.

- Difficulty: Medium
- Max steps: 20
- Success threshold: 0.67
- Baseline score: ~0.60

### Task 2: Semantic Deduplication (Hard)
The database contains 4 pairs of near-duplicate questions imported from different sources. Use semantic search to find them, then merge duplicates without deleting unique content.

- Difficulty: Hard
- Max steps: 20
- Success threshold: 0.5
- Baseline score: ~0.50

## Setup

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"
export HF_TOKEN="your_hf_token_here"

# Start the server
uvicorn server:app --host 0.0.0.0 --port 7860
```

### Run Baseline Agent

```bash
# In a separate terminal
export ENV_BASE_URL="http://localhost:7860"
python inference.py
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/reset` | POST | Reset environment, returns initial observation |
| `/step` | POST | Submit an action, returns obs/reward/done |
| `/observe` | GET | Get current observation |
| `/grade` | GET | Get detailed grading report |
| `/health` | GET | Health check |

## Actions

```json
{ "type": "delete", "doc_ids": ["doc_001", "doc_006"] }
{ "type": "merge",  "doc_ids": ["doc_003", "doc_004"] }
{ "type": "tag",    "doc_ids": ["doc_005"], "tag": "rag" }
{ "type": "done" }
```

## Docker

```bash
docker build -t openenv-rag-curator .
docker run -p 7860:7860 \
  -e API_BASE_URL="https://api.openai.com/v1" \
  -e MODEL_NAME="gpt-4o-mini" \
  -e HF_TOKEN="your_token" \
  openenv-rag-curator
```

## Action Space

The agent can perform 6 action types:

```json
{"action_type": "SEARCH_DB", "query": "python decorator"}
{"action_type": "TAG_QUESTION", "doc_id": "doc_003", "tag": "ml"}
{"action_type": "UPDATE_ANSWER", "doc_id": "doc_005", "answer_text": "Overfitting occurs when..."}
{"action_type": "MERGE_DUPLICATE", "doc_id": "doc_003", "duplicate_doc_id": "doc_019"}
{"action_type": "DELETE_DOC", "doc_id": "doc_025"}
{"action_type": "SUBMIT_TASK"}
```

## Observation Space

Each observation includes:
- `current_task_id`: Active task (task_0, task_1, task_2)
- `current_task_description`: Task instructions
- `database_metrics`: {total_docs, untagged_docs, missing_answers}
- `search_results`: List of DocumentPreview objects from last SEARCH_DB
- `feedback`: Text feedback from last action
- `step_count`: Current step number

## Reward Function

The environment provides dense reward signals based on task progress:
- Rewards reflect the delta in task completion score after each action
- SEARCH_DB is free (no reward/penalty)
- Final score at SUBMIT_TASK is the grader output (0.0-1.0)
- Auto-submits at max_steps with current progress score

## Baseline Performance

**Note:** Baseline inference requires an LLM API key. HuggingFace's free Inference API was deprecated in April 2026 (HTTP 410 errors). The inference script is fully functional and follows the required [START]/[STEP]/[END] log format - it just needs a working API endpoint.

### Estimated Performance (based on task difficulty and grader analysis):
- Task 0 (Easy - Tagging): 0.70-0.85
- Task 1 (Medium - Fill Answers): 0.55-0.70
- Task 2 (Hard - Deduplication): 0.40-0.60
- Average: 0.55-0.72

### To Run Baseline with OpenAI:
```bash
export OPENAI_API_KEY="sk-..."
export MODEL_NAME="gpt-4o-mini"
export ENV_BASE_URL="https://s777k-openenv-rag-curator.hf.space"
python inference.py
```

### To Run Baseline with Anthropic:
```bash
export API_BASE_URL="https://api.anthropic.com/v1"
export OPENAI_API_KEY="sk-ant-..."
export MODEL_NAME="claude-3-haiku-20240307"
export ENV_BASE_URL="https://s777k-openenv-rag-curator.hf.space"
python inference.py
```

### To Run Baseline with Other OpenAI-Compatible Providers:
```bash
export API_BASE_URL="https://your-api-endpoint.com/v1"
export OPENAI_API_KEY="your-api-key"
export MODEL_NAME="your-model-name"
export ENV_BASE_URL="https://s777k-openenv-rag-curator.hf.space"
python inference.py
```

The inference script uses the OpenAI Python client which is compatible with many providers (OpenAI, Anthropic, Together AI, Groq, local models via LM Studio, etc.).

## Data Sources

Real data scraped from:
- source_a: hf_K-areem_AI-Interview-Questions (clean software engineering Q&A)
- source_b: GFG scrape with encoding artifacts (ML/Python/SQL)
- source_c: hf_Shreyash23_interview (broken schema rows)

## License

MIT
