# Fossilize AI

**Before your team's knowledge goes extinct.**

Fossilize AI is an institutional-knowledge agent for software teams. It answers questions about *why* code was built or changed, using real GitHub commit and PR history as its memory — and it proactively watches new pull requests to flag when a change risks repeating a past, documented mistake.

Built for the ServiceNow AI.Accelerate FY26 Capstone (Path B).

---

## The problem

Companies lose institutional knowledge every time someone leaves. The reasoning behind a design decision, a past bug and its fix, a "we tried that already" — all of it usually lives in one person's head, and disappears the moment they're gone. Fossilize AI turns a project's GitHub history into a living, queryable memory, so that knowledge doesn't have to depend on any one person remembering.

---

## What it does

**1. Ask why something was built** — a chat interface grounded in real commit/PR/discussion history. Ask "why was bracket depth tracking added to Leaf" and get an answer that synthesizes multiple PRs, cites its sources, and honestly says when the history doesn't cover something — rather than guessing.

**2. Knowledge-risk dashboard (managers only)** — a computed ranking of which files have concentrated, under-documented contribution history: few contributors, low discussion, high investment. A real signal for bus-factor risk, not a static report.

**3. PR Guardian** — the fully agentic piece. Every time a new pull request opens on the repo, Fossilize AI automatically:
- Detects the PR and which files it touches
- Retrieves relevant history for those files
- Judges whether anything in that history is genuinely relevant to *this* change — not just superficially similar
- If relevant and high-confidence, posts a comment on the PR citing the exact past incident
- If uncertain, queues it for human review instead of guessing
- If nothing relevant exists, stays silent — no noise

No one has to ask it to check. It's watching the repo passively, the same way a long-tenured teammate would.

---

## Architecture

```
GitHub PR event (webhook)
        │
        ▼
FastAPI backend ──► LangGraph orchestration
        │                    │
        │          ┌─────────┴─────────┐
        │     Intent Classifier    PR Guardian
        │          │                    │
        │   ┌──────┼──────┐      Detect → Retrieve
        │   ▼      ▼      ▼      → Judge → Act
        │  RAG  Dashboard Clarify         │
        │   │      │        │      ┌──────┼──────┐
        │   ▼      ▼        ▼    Silent  Post   Human
        │ ChromaDB (role-gated)         Review
        │   │
        └───┴──► Chat UI (index.html)
```

- **Intent Classifier** — an LLM tool-call decides whether a message is a knowledge question, a dashboard request, or too ambiguous to route confidently.
- **RAG pipeline** — GitHub commits/PRs/discussion comments, chunked per-PR on comment boundaries (not raw word count — naive chunking was tested and found to cut arguments mid-sentence), embedded with `all-MiniLM-L6-v2`, stored in ChromaDB.
- **LangGraph** — orchestrates classify → route → retrieve → generate/dashboard/clarify, with a graceful-degrade branch when retrieval confidence is too low.
- **Personas** — two roles (engineer, manager), enforced in code via an authenticated `X-User-Id` header, not by what a user claims in their message.
- **Guardrails** — input and output safety classifiers wrapping the chat endpoint, tested against prompt injection, role-bypass, and out-of-scope requests.
- **Eval suite** — a 20-item golden dataset spanning faithfulness, retrieval accuracy, clarification handling, and safety, scored automatically via LLM-as-judge.

---

## Project structure

```
app/
  main.py              FastAPI app, /api/chat and /webhook/github routes
  graph.py             LangGraph state machine (chat flow)
  intent_classifier.py Tool-calling intent classification
  guardrails.py         Input/output safety checks
  config.py             Environment & path config
  dashboard.py          Knowledge-risk scoring logic
  index.html            Chat UI
ingestion/
  ingest_github.py      Pulls commits/PRs/comments from GitHub
  chunk_data.py          Chunks PR/comment data per-PR, bot-filtered
  embed_and_store.py     Embeds chunks, stores in ChromaDB
pr_guardian/
  detect.py              Fetches PR + changed files
  retrieve.py            Per-file historical retrieval
  judge.py               LLM relevance judgment
  act.py                  Confirmation gate + posting + loop prevention
data/
  raw/, processed/, chroma_db/, users.json
eval/
  golden_dataset.json     20-item eval set
  rubric.md                Scoring rubric (1/3/5 anchors per dimension)
  run_eval.py               Original 10-scenario test suite
  run_llm_judge.py          Automated LLM-as-judge scoring pipeline
  guardrail_demo.py          Guardrail pass/block test cases
benchmark.py               Intent-routing regression check
```

---

## Running it

```powershell
# from project root, with venv activated
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` for the chat UI, or `http://127.0.0.1:8000/docs` for the raw API.

**To re-run ingestion** (rebuild from a different repo, or refresh history):
```powershell
python ingestion/ingest_github.py
python ingestion/chunk_data.py
python ingestion/embed_and_store.py
```

**To run the eval suite:**
```powershell
python eval/run_eval.py
python eval/run_llm_judge.py
python eval/guardrail_demo.py
```

**To connect PR Guardian to a live repo** (via webhook):
```powershell
ngrok http 8000
# register https://<your-ngrok-url>/webhook/github on the target repo's webhook settings
```

---

## Key design decisions

- **Chunking is per-PR, on comment boundaries** — an early naive word-count split cut arguments mid-sentence; fixed by treating each comment as an atomic, unsplittable unit.
- **Bot-authored PRs are filtered at ingestion and chunking** — Dependabot/CI noise was diluting both retrieval and the knowledge-risk dashboard.
- **PR Guardian auto-posts only on high confidence; queues everything else for human review** — a deliberate trust boundary, not a blanket autonomous-vs-manual choice.
- **Dashboard risk weights were validated, not guessed** — the same top-10 files surface across multiple weight combinations, confirming the ranking reflects real signal.
- **Access control is enforced by authenticated role, not by what a user claims in a message** — tested directly against a role-bypass adversarial prompt.
- **MCP tool exposure was scoped out** — a deliberate, acknowledged limitation given time constraints, not an oversight.

---

## Known limitations

- Dashboard reflects currently indexed history, not real-time repo state.
- The chat/dashboard split doesn't yet parse sub-question nuance within a dashboard request (e.g. "show risk excluding bot-only files" returns the same aggregate view).
- LLM-as-judge scoring can itself misjudge highly-detailed-but-accurate answers as fabricated — one such false failure was manually verified against raw source chunks during eval.

---

## Built with

Python, FastAPI, LangGraph, Anthropic Claude, ChromaDB, Sentence-Transformers, GitHub REST API.
