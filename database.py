"""
database.py — Real-world messy RAG knowledge base.

Data sourced from 3 real scraped datasets:
  - source_a: hf_K-areem_AI-Interview-Questions (clean, software engineering)
  - source_b: run_20260325 GFG scrape (encoding artifacts, ML/Python/SQL)
  - source_c: hf_Shreyash23_interview (broken schema — question/answer fields swapped)

Intentional real-world problems baked in:
  - Wrong/missing tags (task_0)
  - Empty or truncated ideal_answers (task_1)
  - Near-duplicate questions from different sources (task_2)
  - Encoding artifacts (â€™, \ufffd) from bad UTF-8 scraping
  - Broken schema rows where question = category label, answer = actual question
  - Junk/navigation rows scraped from page boilerplate
"""
import copy

# ── Ground truth for graders ───────────────────────────────────────────────────

CORRECT_TAGS = {
    # task_0: these 12 docs have wrong or missing tags — agent must fix them
    "doc_003": ["ml"],
    "doc_004": ["ml"],
    "doc_007": ["python"],
    "doc_008": ["python"],
    "doc_011": ["sql"],
    "doc_012": ["sql"],
    "doc_015": ["system-design"],
    "doc_016": ["system-design"],
    "doc_019": ["ml"],
    "doc_020": ["python"],
    "doc_023": ["sql"],
    "doc_024": ["system-design"],
}

CORRECT_ANSWERS = {
    # task_1: these docs have empty or junk ideal_answer — agent must fill them
    "doc_005": "Overfitting occurs when a model learns noise in training data, performing well on training but poorly on unseen data. It can be avoided using regularization, dropout, cross-validation, or simpler models.",
    "doc_009": "A Python decorator is a function that wraps another function to extend its behavior without modifying it directly. Decorators use the @syntax and are commonly used for logging, authentication, and caching.",
    "doc_013": "A SQL JOIN combines rows from two or more tables based on a related column. Types include INNER JOIN (matching rows only), LEFT JOIN (all left + matching right), RIGHT JOIN, and FULL OUTER JOIN.",
    "doc_017": "Docker ensures portability by packaging an application with all its dependencies into a container image. The image runs consistently across any environment that has the Docker runtime installed.",
}

DUPLICATE_PAIRS = [
    # task_2: near-duplicate pairs from different sources — keep first, delete second
    ("doc_003", "doc_019"),   # Both ask about ML vs AI (source_b vs source_c)
    ("doc_007", "doc_020"),   # Both ask about Python decorators (source_a vs source_b)
    ("doc_011", "doc_023"),   # Both ask about SQL JOINs (source_a vs source_b)
    ("doc_015", "doc_024"),   # Both ask about Docker/containers (source_a vs source_b)
]

# ── Initial messy database ─────────────────────────────────────────────────────

INITIAL_DATABASE = {

    # ── CLEAN DOCS (correctly tagged, have answers) ────────────────────────────

    "doc_001": {
        "question": "What are some popular API Gateways used in microservices architectures?",
        "ideal_answer": "Popular API Gateways include Kong, AWS API Gateway, NGINX, Traefik, and Apigee. They handle routing, authentication, rate limiting, and load balancing for microservices.",
        "tags": ["system-design"],
        "source": "source_a",
    },
    "doc_002": {
        "question": "What is the difference between supervised and unsupervised learning?",
        "ideal_answer": "Supervised learning uses labeled data to train models for prediction tasks. Unsupervised learning finds hidden patterns in unlabeled data through clustering or dimensionality reduction.",
        "tags": ["ml"],
        "source": "source_b",
    },

    # ── TASK 0: WRONG OR MISSING TAGS ─────────────────────────────────────────

    "doc_003": {
        "question": "What do you understand by Machine Learning and how does it differ from artificial intelligence and Data Science?",
        "ideal_answer": "Machine Learning is a branch of AI that builds algorithms capable of learning from data. AI is the broader field; Data Science focuses on extracting insights from data using statistical and ML methods.",
        "tags": [],   # MISSING — should be ["ml"]
        "source": "source_b",
    },
    "doc_004": {
        "question": "What is Regularization in machine learning?",
        "ideal_answer": "Regularization reduces model complexity to prevent overfitting by adding a penalty term to the loss function. L1 (Lasso) can zero out weights; L2 (Ridge) shrinks them without elimination.",
        "tags": ["data-science"],   # WRONG — should be ["ml"]
        "source": "source_b",
    },
    "doc_007": {
        "question": "In Python, what is the difference between a list and a tuple?",
        "ideal_answer": "Lists are mutable sequences; tuples are immutable. Tuples are faster and used for fixed data, while lists are used when the collection needs to change.",
        "tags": [],   # MISSING — should be ["python"]
        "source": "source_a",
    },
    "doc_008": {
        "question": "What is a Python generator and how does it differ from a regular function?",
        "ideal_answer": "A generator uses yield to produce values lazily one at a time, saving memory. Unlike regular functions that return all values at once, generators pause execution between yields.",
        "tags": ["general"],   # WRONG — should be ["python"]
        "source": "source_b",
    },
    "doc_011": {
        "question": "What is a SQL JOIN and what are its types?",
        "ideal_answer": "",   # EMPTY — task_1 target
        "tags": [],   # MISSING — should be ["sql"]
        "source": "source_a",
    },
    "doc_012": {
        "question": "What is database indexing and why is it important?",
        "ideal_answer": "An index is a data structure that speeds up query retrieval by allowing the database engine to find rows without scanning the entire table. It trades write speed for read performance.",
        "tags": ["database"],   # WRONG — should be ["sql"]
        "source": "source_b",
    },
    "doc_015": {
        "question": "How does Docker ensure application portability across environments?",
        "ideal_answer": "",   # EMPTY — task_1 target
        "tags": [],   # MISSING — should be ["system-design"]
        "source": "source_a",
    },
    "doc_016": {
        "question": "What is the difference between REST and GraphQL APIs?",
        "ideal_answer": "REST uses fixed endpoints returning full resources; GraphQL uses a single endpoint where clients specify exactly what data they need, reducing over-fetching and under-fetching.",
        "tags": ["api"],   # WRONG — should be ["system-design"]
        "source": "source_b",
    },
    "doc_019": {
        # DUPLICATE of doc_003 — different source, slightly different wording
        "question": "machine learning interview question",   # broken schema from source_c
        "ideal_answer": "How does Machine Learning differ from traditional AI programming approaches?",  # answer field = actual question (schema swap)
        "tags": [],
        "source": "source_c",
    },
    "doc_020": {
        # DUPLICATE of doc_007 — encoding artifact version
        "question": "What is a Python decorator? How does it workâ€™s internally?",  # encoding artifact
        "ideal_answer": "",   # EMPTY — task_1 target
        "tags": [],   # MISSING — should be ["python"]
        "source": "source_b",
    },
    "doc_023": {
        # DUPLICATE of doc_011
        "question": "Explain SQL JOIN operations and when to use each type.",
        "ideal_answer": "Used to retrieve related data from multiple tables.",
        "tags": ["database"],   # WRONG — should be ["sql"]
        "source": "source_b",
    },
    "doc_024": {
        # DUPLICATE of doc_015
        "question": "What are Docker containers and how do they differ from virtual machines?",
        "ideal_answer": "Containers share the host OS kernel and are lightweight; VMs include a full OS and are heavier. Docker containers start in milliseconds vs minutes for VMs.",
        "tags": [],   # MISSING — should be ["system-design"]
        "source": "source_b",
    },

    # ── TASK 1: EMPTY / TRUNCATED ANSWERS ─────────────────────────────────────

    "doc_005": {
        "question": "What is overfitting in machine learning and how can it be avoided?",
        "ideal_answer": "",   # EMPTY — agent must fill
        "tags": ["ml"],
        "source": "source_b",
    },
    "doc_009": {
        "question": "What is a Python decorator and how is it used?",
        "ideal_answer": "",   # EMPTY — agent must fill
        "tags": ["python"],
        "source": "source_a",
    },
    "doc_013": {
        "question": "Explain the different types of SQL JOINs with examples.",
        "ideal_answer": "",   # EMPTY — agent must fill
        "tags": ["sql"],
        "source": "source_b",
    },
    "doc_017": {
        "question": "How does Docker ensure application portability?",
        "ideal_answer": "",   # EMPTY — agent must fill
        "tags": ["system-design"],
        "source": "source_a",
    },

    # ── JUNK ROWS (scraped page boilerplate / failed imports) ─────────────────

    "doc_025": {
        "question": "Additional Resources",
        "ideal_answer": "Practice Coding Best Machine Learning Courses Best Data Science Courses Free Deep Learning Course",
        "tags": [],
        "source": "source_b",
    },
    "doc_026": {
        "question": "Interview Resources",
        "ideal_answer": "NLP Interview Questions Data Science Interview Questions Free Deep Learning Tutorial",
        "tags": [],
        "source": "source_b",
    },
    "doc_027": {
        "question": "Conclusion",
        "ideal_answer": "The above-listed questions are the basics of machine learning. Machine learning is advancing so fast.",
        "tags": [],
        "source": "source_b",
    },

    # ── GOOD DOCS (correctly tagged, complete answers) ────────────────────────

    "doc_006": {
        "question": "What is the difference between precision and recall in ML evaluation?",
        "ideal_answer": "Precision is the fraction of true positives among predicted positives. Recall is the fraction of true positives among all actual positives. F1-score is their harmonic mean.",
        "tags": ["ml"],
        "source": "source_b",
    },
    "doc_010": {
        "question": "What are Python list comprehensions and when should you use them?",
        "ideal_answer": "List comprehensions provide a concise way to create lists using a single line: [expr for item in iterable if condition]. Use them for simple transformations; avoid for complex logic.",
        "tags": ["python"],
        "source": "source_b",
    },
    "doc_014": {
        "question": "What is database normalization and what are the normal forms?",
        "ideal_answer": "Normalization organizes a database to reduce redundancy. 1NF eliminates repeating groups; 2NF removes partial dependencies; 3NF removes transitive dependencies; BCNF is a stricter 3NF.",
        "tags": ["sql"],
        "source": "source_a",
    },
    "doc_018": {
        "question": "What is the difference between monolithic and microservices architecture?",
        "ideal_answer": "Monolithic apps are single deployable units — simple but hard to scale. Microservices split functionality into independent services that communicate via APIs, enabling independent scaling and deployment.",
        "tags": ["system-design"],
        "source": "source_a",
    },
    "doc_021": {
        "question": "What is gradient descent and how does it work?",
        "ideal_answer": "Gradient descent is an optimization algorithm that minimizes a loss function by iteratively moving in the direction of steepest descent (negative gradient). Learning rate controls step size.",
        "tags": ["ml"],
        "source": "source_b",
    },
    "doc_022": {
        "question": "What is the Global Interpreter Lock (GIL) in Python?",
        "ideal_answer": "The GIL is a mutex in CPython that allows only one thread to execute Python bytecode at a time. It simplifies memory management but limits true multi-threading for CPU-bound tasks.",
        "tags": ["python"],
        "source": "source_b",
    },
}


def get_fresh_database() -> dict:
    """Always returns a clean deep copy — used in reset()."""
    return copy.deepcopy(INITIAL_DATABASE)
