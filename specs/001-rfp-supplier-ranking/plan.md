# Implementation Plan: Agentic RFP Evaluation and Supplier Ranking

**Branch**: `001-rfp-supplier-ranking` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-rfp-supplier-ranking/spec.md`

## Summary

A Streamlit app where a procurement evaluator uploads 2–10 supplier proposal PDFs with metadata;
a LangGraph parent graph (`rfp_run_graph`) snapshots the active SQLite criteria, fans out one
`supplier_eval` subgraph per supplier via `Send()` (extract PDF text → build prompt → LLM judge with
JSON output at temperature 0 → Pydantic validation → at most one retry → normalize), then runs
pure-Python `score → benchmark → rank` functions and persists the full result JSON under one
`rfp_run_id`. The UI only calls `graph.stream()` and renders progress, leaderboard, scorecards,
run details, and the JSON download. Full architecture: [docs/architecture.md](../../docs/architecture.md).

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: streamlit, langgraph, langchain-core, langchain-openai, pydantic v2,
pymupdf, reportlab (scripts only), pytest

**Storage**: SQLite via stdlib `sqlite3`; tables `evaluation_criteria`, `rfp_runs`,
`supplier_results`; created + seeded idempotently at app start (`data/rfp_eval.db`, git-ignored)

**Testing**: pytest; business rules tested against pure functions; LLM stubbed with a fake chat
model returning canned strings; no network or API key needed

**Target Platform**: Streamlit Community Cloud (Linux, ephemeral disk); local macOS/Linux for dev

**Project Type**: Single-project web app (Streamlit) + Python package `rfp_eval`

**Performance Goals**: 4 suppliers × 2–4 pages complete in < 3 min with no retries (SC-002);
suppliers evaluated in parallel by the `Send()` fan-out

**Constraints**: LLM attempt timeout 90 s; exactly 1 evaluation retry; up to 3 busy-retries
(5/10/20 s) that do not consume the evaluation retry; client-level retries disabled
(`max_retries=0`); temperature 0; uploads ≤ 10 MB, ≥ 200 non-whitespace chars; no PDF or full text
persisted; secrets only from `st.secrets` / env

**Scale/Scope**: single role, demo scale, 2–10 suppliers per run, 5 seeded criteria

**LLM provider**: OpenAI via `langchain_openai.ChatOpenAI`, model from `OPENAI_MODEL`
(default `gpt-4.1-nano`, which supports `temperature=0`), JSON mode
(`response_format={"type":"json_object"}`); raw string kept for FR-033a, then validated by our own
Pydantic models (see [research.md](research.md) R1).

No NEEDS CLARIFICATION remain.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle / Constraint | Design compliance | Status |
|---|---|---|---|
| I | LLM judges, Python decides | LLM is called only in `supplier_eval.call_llm`; prompt asks only for per-criterion score/justification/evidence, risks, summary. `score`, `benchmark`, `rank`, `persist` are deterministic; `rfp_eval/scoring` imports no LLM/LangGraph. | PASS |
| II | Determinism | Stable sort key `(-ppi, submission_date, -experience_rating, name.casefold())`; fan-in results re-sorted by `supplier_index` before scoring; PPIs compared as `fractions.Fraction` so equal values tie exactly; temperature 0; full precision stored, round only in UI. | PASS |
| III | Evidence-grounded & traceable | Each subgraph sees only its own supplier's text; evidence substring check (whitespace/case-normalized) flags warnings; full result JSON with criteria snapshot, raw responses, metrics, warnings, tie-break text persisted and downloadable. | PASS |
| IV | Untrusted LLM output | `validate` node parses with Pydantic (lenient raw model → strict normalized model); every fix emits a structured `Warning`; failures produce an "evaluation failed" zero scorecard instead of raising. | PASS |
| V | LangGraph orchestration | Parent `rfp_run_graph` + `supplier_eval` subgraph per supplier; typed `TypedDict` state; parallel-written keys `scorecards`, `warnings`, `progress` use `operator.add` followed by deterministic sort; no module-level run state (LLM client/DB path passed via `config["configurable"]`). | PASS |
| VI | Configuration as data | Criteria in SQLite; prompt built from snapshot; Evaluate blocked unless active weights = 100; snapshot taken once in `load_criteria`. | PASS |
| VII | Test-first business rules | `tasks.md` will order tests in `tests/unit/test_scoring.py`, `test_ranking.py`, `test_validation.py`, `test_criteria.py` before the implementing modules; tests use stubs only. | PASS |
| — | Tech & data constraints | Python 3.11, Streamlit, sqlite3, LangGraph, Pydantic; synthetic PDFs via reportlab script; `.env`, `.streamlit/secrets.toml` git-ignored; `requirements.txt` only. | PASS |

**Post-design re-check (after Phase 1)**: PASS — data-model, contracts, and architecture keep all
LLM calls inside `call_llm`, all arithmetic in `rfp_eval/scoring`, and all parallel keys reduced
and re-sorted. No violations; Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-rfp-supplier-ranking/
├── plan.md              # This file
├── research.md          # Phase 0 decisions
├── data-model.md        # Entities, Pydantic schemas, SQLite DDL, state transitions
├── quickstart.md        # Run/validation guide
├── contracts/
│   ├── llm-output.schema.json   # JSON the LLM must return
│   ├── graph-state.md           # RFPRunState / SupplierEvalState contract + stream events
│   └── result-json.md           # Downloaded/persisted run result shape
└── tasks.md             # /speckit-tasks output (not created here)

docs/
└── architecture.md      # Mermaid graphs, state schemas, node table, SQLite, data flow, component map
```

### Source Code (repository root)

```text
app.py                         # Streamlit UI: init DB, criteria editor, uploads, graph.stream(), render
rfp_eval/
├── __init__.py
├── config.py                  # settings from st.secrets/env (API key, model, DB path, timeouts)
├── schemas/
│   ├── __init__.py
│   ├── criteria.py            # Criterion, CriteriaSnapshot
│   ├── supplier.py            # SupplierInput (metadata + transient pdf bytes)
│   ├── llm.py                 # RawLLMEvaluation (lenient), CriterionJudgement
│   ├── scorecard.py           # CriterionResult, Scorecard, AttemptRecord
│   ├── results.py             # PeerMetrics, RankedSupplier, RunResult
│   └── warnings.py            # Warning, IssueType
├── tools/
│   ├── __init__.py
│   ├── pdf_tool.py            # PyMuPDF extract_text(bytes) -> pages, empty pages, truncation
│   ├── intake.py              # pre-run validation (FR-005/007): type, size, text, dupes, dates
│   └── validation.py          # parse + normalize raw LLM output -> Scorecard + warnings
├── agents/
│   ├── __init__.py
│   ├── prompt.py              # build_messages(snapshot, supplier_name, text)
│   └── evaluator.py           # call_llm with timeout, busy-retry backoff, raw capture
├── scoring/
│   ├── __init__.py
│   ├── score.py               # absolute_score
│   ├── benchmark.py           # benchmarks, gap, relative %, PPI
│   └── rank.py                # rank_suppliers, tie-break explanation
├── graph/
│   ├── __init__.py
│   ├── state.py               # RFPRunState, SupplierEvalState (TypedDict + reducers)
│   ├── supplier_eval.py       # subgraph build
│   └── rfp_run_graph.py       # parent graph build (Send fan-out, error path)
└── db/
    ├── __init__.py
    ├── schema.sql
    ├── connection.py          # connect(path), init_db (idempotent create + seed), mark_interrupted
    └── repository.py          # criteria CRUD, runs, supplier_results, history
scripts/
├── seed_db.py                 # CLI wrapper around init_db
└── make_synthetic_pdfs.py     # reportlab: 4 fictional proposals -> data/samples/
data/samples/                  # Apex_Systems.pdf, BrightPath_Tech.pdf, NexaWorks.pdf, Orbit_Digital.pdf
tests/
├── conftest.py                # tmp DB, fake LLM, sample snapshot
├── fixtures/llm_responses/    # canned good/malformed/missing/out-of-range/non-numeric JSON
├── unit/                      # test_scoring, test_ranking, test_validation, test_intake, test_criteria, test_pdf_tool
└── integration/               # test_graph_end_to_end (fake LLM), test_persistence
requirements.txt
.streamlit/secrets.toml.example
.gitignore                     # .env, .streamlit/secrets.toml, data/*.db
```

**Structure Decision**: Single Python package `rfp_eval` with the six sub-packages requested
(`graph, agents, tools, scoring, db, schemas`), a thin `app.py`, two scripts, and `tests/`.
`scoring` is pure (no LangGraph/LLM imports) so business rules are tested directly.

## Complexity Tracking

No constitution violations to justify.
