# Agentic RFP Evaluation & Supplier Ranking

A Streamlit app that reads supplier RFP PDFs, has an LLM score each one against criteria stored in SQLite, then uses deterministic Python to benchmark suppliers against each other and rank them. Every score can be traced back to its evidence.

**Stack:** Streamlit · SQLite · LangGraph (orchestrator + subgraph) · OpenAI (JSON mode, temperature 0) · PyMuPDF · Pydantic

## Setup
```bash
pip install -r requirements.txt
python scripts/seed_db.py               # creates rfp_eval.db + sample criteria (the app also does this on start)
python scripts/make_synthetic_pdfs.py   # writes 4 fictional supplier PDFs to data/samples/
export OPENAI_API_KEY=sk-...            # or put it in .streamlit/secrets.toml
streamlit run app.py
pytest -q                                # business-rule + end-to-end graph tests (no API key needed)
```

## Bring your own key (BYOK)
Enter your OpenAI API key in the sidebar and pick a model. **Test key** checks it without using any tokens. The key is kept only in your browser session and is never written to SQLite, logs or exported JSON. If you leave the field blank, the app uses the owner's `OPENAI_API_KEY` from Streamlit secrets, if one is set. When the key is invalid, the run is blocked before a run ID is created.

## Deploy (Streamlit Community Cloud)
1. Push this repo to GitHub.
2. Go to share.streamlit.io, choose **Create app**, pick this repo and branch `main`, and set the main file to `app.py`.
3. (Optional) Open **Advanced settings → Secrets** and add `OPENAI_API_KEY = "sk-..."` as a default key. Otherwise users bring their own key in the sidebar.
4. Click Deploy. The SQLite DB is created and seeded automatically at startup. Community Cloud storage is temporary, so run history resets when the app restarts.

## Architecture
```
Parent graph (Orchestrator) — RFPRunState
START → load_criteria (weights must total 100) → create_run (RFP_RUN_ID, status RUNNING)
      → Send() × N suppliers ─► supplier_eval SUBGRAPH (parallel)
      → score → benchmark → rank → persist (status COMPLETED) → END

supplier_eval subgraph — SupplierEvalState
extract_pdf (Document Tool) → evaluate (Evaluation Agent / LLM) ─(bad JSON, retry once)─┐
                                   ▲─────────────────────────────────────────────────────┘
                              → normalize (Validation Tool) → END
```
| Brief component | Implementation | LLM? |
|---|---|---|
| Orchestrator Agent | `rfp_eval/graph.py` parent `StateGraph` | No |
| Document Tool | `rfp_eval/pdf_tool.py` (PyMuPDF) | No |
| Evaluation Agent | `rfp_eval/evaluator.py` (prompt + ChatOpenAI JSON mode) | **Yes** |
| Validation Tool | `rfp_eval/validation.py` (Pydantic + normalization) | No |
| Ranking Tool | `rfp_eval/scoring.py` (pure Python) | No |

**Shared state:** the subgraph shares only `scorecards` and `warnings` with the parent. Both use `operator.add` reducers, so parallel supplier results merge safely. The subgraph's PDF text, raw LLM output and attempt count stay private to it.

## Formulas
- Absolute score = Σ (score / max_score) × weight
- Benchmark = highest validated score per criterion across all suppliers in the run
- Gap = supplier score − benchmark (0 for the leader, otherwise negative)
- Relative % = score / benchmark × 100. **If the benchmark is 0**, relative % = 0 for all suppliers and a warning is recorded. This can't change the order, because every supplier gets the same value.
- PPI = Σ (weight × relative %) / Σ weight
- **Tie-break:** higher PPI → earlier submission date → higher experience rating → supplier name A–Z. The sort is stable and ranks are 1..N with no shared ranks. The leaderboard explains why each supplier sits below the one above it.

## Validation rules
- **Before a run:** files must be PDF and ≤10 MB; supplier names are required and unique; submission dates can't be in the future; experience rating is 1–5; active weights must total 100.
- **LLM output:** if the JSON is malformed, the call is retried once. After that, a missing criterion gets score 0, an out-of-range score is clipped to 0..max, a non-numeric score becomes 0, and unknown or duplicate criteria are ignored. Each of these fixes is recorded as a warning.
- An unreadable PDF or a failed LLM call scores 0 for that supplier only and adds a warning. The run itself still completes.

## Assumptions
- Criteria are reloaded at evaluation time and saved as a snapshot in the run's JSON, so editing criteria later doesn't change past runs.
- All supplier documents are fictional (see `scripts/make_synthetic_pdfs.py`).
- Uploaded PDFs are not stored. Only the results are saved.

## Database
`evaluation_criteria(criterion_id, name, description, weight, max_score, is_active)` · `rfp_runs(rfp_run_id, created_at, status, result_json)` · `supplier_results(rfp_run_id, supplier_name, submission_date, experience_rating, absolute_score, ppi, final_rank, result_json)`

## Demo checklist
1. **Successful run:** upload the 4 PDFs in `data/samples/`, then check the leaderboard, scorecards and JSON download.
2. **Error case:** in the Criteria tab, deactivate a criterion. The weight total no longer equals 100 and saving is blocked. Or upload two suppliers with the same name, and Evaluate is disabled with an error message.
