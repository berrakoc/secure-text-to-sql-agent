# Text-to-SQL Assistant

Ask a database questions in plain English. Get safe, verified SQL back.

**On a 51-question evaluation set: 96% execution accuracy, and 100% of destructive queries blocked.**

This is a natural-language-to-SQL system built with production concerns in mind. It doesn't just turn questions into SQL — it refuses to run dangerous queries, checks its own answers for correctness, and tells you how much to trust each result.

---

## Why this project

Most text-to-SQL demos stop at "question in, SQL out." That's the easy part. The hard part is everything that makes such a system safe to put in front of real users:

- What happens when the model writes a `DELETE` or `DROP` query?
- What if the SQL runs fine but answers the *wrong* question?
- How does a user know whether to trust the result?

This project is built around those three problems. It has a safety layer that blocks destructive operations, a hallucination-detection layer that verifies each answer, and a confidence score that explains itself.

---

## How it works

A question flows through the system in five stages. Each stage can stop the process early if something is wrong.

**1. Schema-aware prompt building.**
The system reads the database structure automatically (tables, columns, relationships) and turns it into context the model can use. For large schemas, it uses embeddings to pick only the tables relevant to the question, instead of sending everything.

**2. SQL generation with structured output.**
The model returns not just SQL, but also a short explanation and the tables it used — all as structured JSON. If a question is ambiguous (like "who is our best customer?"), the system asks for clarification instead of guessing.

**3. Safety guardrails.**
Before any query runs, it passes through a safety layer. This blocks anything that isn't a read-only `SELECT` — no `DROP`, `DELETE`, `INSERT`, or `UPDATE`, and no stacked queries. As a second line of defense, the database itself is opened in read-only mode, so even a query that slipped through couldn't change data.

**4. Read-only execution.**
The safe query runs and returns results, along with timing and the query plan.

**5. Hallucination detection.**
The system checks its own answer using several independent signals: it translates the SQL back into a question and compares it to the original, runs sanity checks on the result, and for complex queries generates a second SQL a different way to see if both agree. These combine into a single confidence score that explains itself.

---

## Architecture

The project is split into focused modules:

| Folder | Responsibility |
|--------|----------------|
| `db/` | Read the schema; pick relevant tables using embeddings |
| `generation/` | Build the prompt and generate SQL |
| `safety/` | Guardrails and read-only execution |
| `detection/` | Hallucination detection and confidence scoring |
| `api/` | FastAPI service exposing the pipeline over HTTP |
| `ui/` | Streamlit web interface |
| `eval/` | Golden dataset and the evaluation engine |

#### The core logic lives in `pipeline.py`, which ties every stage together. The API and UI are thin layers on top of it — the same logic runs whether you call it from the command line, over HTTP, or through the web interface.
---

## Getting started

### Requirements

- Python 3.11+
- An OpenAI API key

### Setup

1. Clone the repository and enter it:

   ```bash
   git clone https://github.com/berrakoc/secure-text-to-sql-agent
   cd Text-to-SQL
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # on Windows: venv\Scripts\activate
   ```

3. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Add your OpenAI API key to a `.env` file in the project root:

   ```env
   OPENAI_API_KEY=your_key_here
   ```

The database (a sample music store called Chinook) is included as `data/chinook.db`, so there's nothing else to set up.

### Running the system

The system has three ways to run, all built on the same core pipeline.

**Command line** — ask a single question:

```bash
python3 pipeline.py
```

**API** — start the FastAPI service, then open the docs:

```bash
uvicorn api.main:app --reload
```

Then visit `http://127.0.0.1:8000/docs` for an interactive API playground.

**Web interface** — with the API running, start the Streamlit app in a second terminal:

```bash
streamlit run ui/app.py
```

### Running the evaluation

To reproduce the accuracy and safety numbers:

```bash
python3 -m eval.run_eval
```

This runs all 51 test cases and the guardrail checks, then prints a summary.

---

## A note on the database

This project uses SQLite for speed and simplicity — the whole database is a single file, with no server to set up. Because all database access goes through SQLAlchemy, moving to PostgreSQL for production would mean changing one connection string, not rewriting the code.

---

## Evaluation

The system is tested against a hand-built golden dataset of 51 questions, each with a verified correct answer. The questions cover seven categories, from simple lookups to deliberately tricky cases.

Accuracy is measured by **execution match**: does the system's result match the correct answer, regardless of how the SQL is written? This is fairer than comparing SQL text, since there are many correct ways to write the same query.

### Results by category

| Category | Score | What it tests |
|----------|-------|---------------|
| Simple lookups | 10/10 (100%) | Basic counts and listings |
| Aggregations | 8/8 (100%) | `GROUP BY`, `SUM`, `AVG` |
| Joins | 10/10 (100%) | Multi-table queries |
| Date filters | 5/5 (100%) | Filtering by year and quarter |
| Ambiguous | 5/5 (100%) | Should ask, not guess |
| Unanswerable | 5/5 (100%) | Data not in the database |
| Hard (adversarial) | 6/8 (75%) | Nested aggregation, tricky wording |
| **Overall** | **49/51 (96%)** | |

### Safety

Every destructive query in the test set was blocked:

| | Result |
|--|--------|
| Dangerous queries blocked | **7/7 (100%)** |

This includes `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `TRUNCATE`, and stacked-query injection attempts.

### What the failures taught me

The two failures are in the hardest category, and both are informative rather than random:

- **Nested aggregation.** For "how many customers have spent more than $40?", the system correctly found the right customers but *listed* them instead of *counting* them. It struggles to wrap an aggregation inside another one.
- **Subtle ambiguity.** For "total spending of customers in the USA," the system picked one interpretation instead of asking which one the user meant (billing country vs. customer country). Its ambiguity detection catches obvious cases but misses subtle ones.

I kept both failures in the results rather than hiding them. Knowing exactly where and why a system fails is more useful than a perfect-looking score.

---

## Tech stack

| Area | Tools |
|------|-------|
| Language | Python 3.11 |
| LLM | OpenAI (`gpt-4o-mini`), embeddings for table retrieval |
| Database | SQLite (Chinook sample data), via SQLAlchemy |
| API | FastAPI |
| Interface | Streamlit |
| SQL parsing | sqlparse |
| Evaluation | Custom golden-dataset harness |

## What I'd do next

A few directions this could grow:

- **Move to PostgreSQL** for a production-grade database, and add row-scan limits using its query planner.
- **Improve nested-aggregation handling** — the main weakness the evaluation revealed.
- **Sharpen ambiguity detection** to catch subtle cases, not just obvious ones.
- **Feed real usage back in** — the feedback loop already collects correct/incorrect labels that could become new test cases and few-shot examples.