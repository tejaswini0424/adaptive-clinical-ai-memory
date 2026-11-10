# Clinical AI Memory Intelligence Platform

A local research and educational application for persistent clinical literature retrieval and human-reviewed evidence updating. It is not a diagnosis or treatment system.

## Public deployment

Live app: https://clinical-ai-memory.vercel.app

Vercel serves `index.py` (FastAPI) and `public/index.html` (responsive browser frontend). All eight modules use the same authenticated backend endpoints as the Streamlit interface. A free Neon PostgreSQL database stores accounts, documents, memories, and histories. Vercel sign-in protection is disabled; anyone can open the link and register an app account without approval. App login keeps each account's data separate.

The original Streamlit interface remains available locally using the commands below. Vercel dependencies are configured in `pyproject.toml`; local Streamlit dependencies remain in `requirements.txt`. Hosted database URLs are environment variables, never committed. `.vercelignore` excludes local databases, environments, logs, and test data.

Redeploy from this linked workspace with `npx vercel --prod`. The hosted `DATABASE_URL` must remain configured. Local SQLite is explicitly rejected when running on Vercel to prevent silent loss of persistent data. Vercel imposes its own request size and execution limits; uploaded files may encounter those limits below the local API's 10 MB cap.

Public smoke test: `.\.venv\Scripts\python tests\production_smoke.py` (creates a synthetic verification account). The frontend JavaScript syntax and backend workflow tests are also validated.

## Problem and objectives

Long-lived knowledge repositories lose provenance and can retain outdated passages. This project keeps documents, searchable memories, retrieval activity, and evidence versions together, with explicit review before replacing an existing record.

## Solution and architecture

Streamlit → authenticated FastAPI REST API → SQLAlchemy / SQLite. Retrieval chunks stored documents into overlapping passages and ranks them using TF-IDF cosine similarity by default. Optional Sentence Transformers embeddings and FAISS provide semantic retrieval. The passage index is rebuilt from persisted database records for each search, so updates and deletions are immediately reflected without stale index files. This favors small research repositories over large-scale deployment.

Extractive summaries cite document IDs and appear separately from the original retrieved passages. There is no paid API requirement and no external LLM dependency. No clinical claim is independently verified by the application.

## Installation

Python 3.11+ recommended. Tested here with Python 3.14 on Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If your Python distribution cannot bootstrap pip inside the environment:

```powershell
python -m pip --python .venv\Scripts\python.exe install -r requirements.txt
```

## Run

From this project directory, in two terminals:

```powershell
.\.venv\Scripts\python -m uvicorn backend.main:app --reload
```

```powershell
.\.venv\Scripts\python -m streamlit run app.py
```

Dashboard: http://localhost:8501 · API documentation: http://localhost:8000/docs

Create any account with nonempty credentials. No password complexity or arbitrary minimum length is enforced. Select **Load synthetic demo** on the overview for sample content. Demo passages are invented educational cases; linked public reading resources are not represented as ingested or verified source text. Upload downloaded public PDFs/TXT or paste evidence with its URL to retrieve actual source material.

Environment settings are documented in `.env.example`; set them in the shell (the file is an example, not automatically loaded):

```powershell
$env:API_URL='http://127.0.0.1:8000'
$env:EMBEDDING_BACKEND='tfidf'
```

Optional semantic engine, preferably on Python 3.11 or 3.12 where ML wheels are widely available:

```powershell
python -m pip install -r requirements-semantic.txt
$env:EMBEDDING_BACKEND='sentence-transformers'
```

The model downloads on first semantic query. TF-IDF runs offline after dependency installation. Semantic mode reports a clear error if model dependencies/downloads are unavailable; switch back to `tfidf`. The default is lexical similarity, not neural semantic understanding.

## Modules

* **Overview:** actual counts and charts from the signed-in account; no invented success statistics.
* **Repository:** PDF/TXT extraction (10 MB maximum), metadata, category search, editing, deletion, and synchronized knowledge records. Scanned PDFs need OCR before upload.
* **Memory:** persistent short-term, long-term, semantic, and episodic entries; ranked search, access counts, exact duplicate suppression, editable content, deletion, and history. Short-term entries remain stored for audit but leave active search after 24 hours. Query episodes are automatically recorded. Memory kinds describe organization; they are not distinct trained cognitive models.
* **Retrieval and chat:** ranked stored passages, relevance scores, source dates, extractive explanations, related memories, and session-local chat history. Similarity scores are not confidence or evidence quality measures.
* **Evidence:** new document intake, target comparison, publication chronology, pending review, old/new snapshots, acceptance/rejection, and version history. All comparisons flag possible disagreement for review. Text overlap cannot establish clinical contradictions. Acceptance explicitly replaces the target content/source/date; rejection leaves the target unchanged. Manually edited records are also versioned.
* **Agents:** five synchronous logical roles instrumented in the activity table: Memory, Retrieval, Evidence, Summarization, Update. These are local functions rather than autonomous background workers.
* **Reports:** CSV exports and charts for memories, documents, retrievals, evidence, agent tasks, memory history, and versions. Spreadsheet formula prefixes are escaped on export.

## Authentication and persistence

Passwords use salted scrypt hashes. Random 12-hour bearer sessions are stored as SHA-256 token hashes; logout revokes the current session. Every data endpoint restricts records to the authenticated owner. SQLite foreign keys are enabled. Accounts self-register without approval. UI tokens are held in Streamlit session state; browser/session resets require login again.

Tables: `users`, `sessions`, `clinical_documents`, `knowledge_records`, `agent_memories`, `memory_history`, `evidence_records`, `evidence_versions`, `retrieval_history`, `agent_activity`. Owner and document/version foreign keys link records. UTC timestamps are stored; the dashboard clock displays Asia/Kolkata.

## Folder structure

```text
app.py
requirements.txt
requirements-semantic.txt
.env.example
backend/
  __init__.py
  main.py           # REST endpoints and instrumented logical agents
  auth.py           # password hashing and expiring sessions
  database.py       # database configuration
  models.py         # SQLAlchemy schema
  retrieval.py      # passage ranking and extractive summaries
frontend/styles.css
data/sample_evidence.json
database/           # automatically initialized SQLite files
reports/            # validation logs and dependency inventory
tests/test_workflows.py
```

## Testing

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m compileall -q app.py backend tests
```

Tests use a separate uniquely named workspace database and cover account isolation, password hashing, login/logout, memory/history, document upload, retrieval/no-match behavior, CSV reports, evidence review/version preservation, demo initialization, and date validation.

## Screenshots

Launch the dashboard and load the demo to inspect the overview, evidence review desk, and repository. No fabricated screenshots are included.

## Deployment and remaining limits

The public Vercel deployment uses the browser interface and PostgreSQL described above. Before handling real sensitive data, add production controls such as rate limiting, monitoring, backups, security review, and a suitable data protection process. Keep this demonstration on synthetic or public non-sensitive material. Public evidence is ingested by upload/manual entry; no scheduled web crawler is included. There is no external generative model or automated clinical conflict adjudication. The local Streamlit CSS uses an optional Google font and otherwise falls back to sans-serif.

Installed package versions are recorded in `reports/installed-dependencies.txt`.
