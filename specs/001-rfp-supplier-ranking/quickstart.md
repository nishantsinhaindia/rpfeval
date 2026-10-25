# Quickstart & Validation Guide

## Prerequisites

- Python 3.11, an OpenAI API key (only for real runs; tests need none).

## Setup

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # set OPENAI_API_KEY (or export it)
python scripts/make_synthetic_pdfs.py      # writes data/samples/*.pdf (4 suppliers)
python scripts/seed_db.py                  # optional; app.py also creates + seeds on start
```

## Validate business rules (offline)

```bash
pytest -q                                   # must pass with no network / API key
pytest tests/unit/test_scoring.py tests/unit/test_ranking.py -q   # formulas, zero benchmark, 4 tie levels
pytest tests/unit/test_validation.py -q     # malformed, missing, non-numeric, clipped, unknown/dup ids, no evidence
pytest tests/integration/test_graph_end_to_end.py -q   # full graph with fake LLM incl. retry + busy-retry + all-failed
```

Expected: all green; SC-003 determinism test recomputes 100× with identical output.

## Run the app

```bash
streamlit run app.py
```

| Scenario | Steps | Expected |
|---|---|---|
| US1 happy path | Upload the 4 files from `data/samples/`, fill dates (past) and ratings, Evaluate | One new run ID; per-supplier progress; leaderboard of 4 with ranks 1–4 (< 3 min) |
| US2 explain | Open each scorecard and Run details; Download JSON | Score/benchmark/gap/relative %/weight/evidence shown; JSON matches [contracts/result-json.md](contracts/result-json.md) |
| US4 weights | Deactivate a criterion so total ≠ 100 | Evaluate blocked: "Active weights total 80; must equal 100" |
| FR-005 | Upload 1 PDF | "At least two supplier proposals are required" |
| FR-007 | Upload a renamed .txt, same file twice, future date, blank name | Each blocked with a named message |
| US5 history | Run twice, open history, reopen first | Identical leaderboard and JSON as originally shown |
| FR-036 | Unset `OPENAI_API_KEY` | Evaluate blocked with configuration message; criteria/history still usable |

## Deploy (Streamlit Community Cloud)

Point the app at `app.py`, add `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`) in app secrets.
On first load the DB is created and seeded automatically (SC-009).
