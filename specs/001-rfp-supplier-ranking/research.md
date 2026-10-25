# Research: Agentic RFP Evaluation and Supplier Ranking

All Technical Context items are resolved. Each decision lists rationale and alternatives.

## R1. LLM call & structured output

- **Decision**: `ChatOpenAI(model=OPENAI_MODEL or "gpt-4.1-nano", temperature=0, timeout=90,
  max_retries=0).bind(response_format={"type": "json_object"})`. Keep `message.content` as the raw
  string (FR-033a), then parse/validate with our own Pydantic models in the `validate` node.
- **Rationale**: JSON mode guarantees syntactically JSON-ish output while leaving the raw text
  available for storage and for our lenient normalization (non-numeric scores, unknown IDs,
  duplicates). `with_structured_output(strict)` would reject or coerce bad output before we can
  record warnings. `max_retries=0` satisfies "no other automatic retries" (FR-014).
- **Alternatives**: `with_structured_output(include_raw=True)` — workable but hides partial
  failures inside `parsing_error`; `gpt-5-nano` — reasoning model, does not accept
  `temperature=0`, violates Principle II.

## R2. Busy / timeout / retry policy

- **Decision**: `agents/evaluator.py::invoke_with_busy_retry(llm, messages, sleep=time.sleep)`
  catches `openai.RateLimitError`, `APIConnectionError`, `InternalServerError` (5xx) → waits 5, 10,
  20 s (max 3 resends) and appends a `busy_retry` warning each time. `APITimeoutError` or busy after
  3 resends → attempt failed. The subgraph's `validate → call_llm` edge provides the single
  evaluation retry (`attempts < 2`). `sleep` injectable so tests run instantly.
- **Rationale**: Separates infrastructure retries from evaluation retries exactly as FR-014 says.

## R3. LangGraph fan-out and merge

- **Decision**: Conditional edge from `create_run` returns
  `[Send("supplier_eval", {...per-supplier input}) for s in suppliers]`. `supplier_eval` is a
  compiled subgraph added as a node; its output keys `scorecards`, `warnings`, `progress` are
  `Annotated[list, operator.add]` in both states. After fan-in, `score` sorts scorecards by
  `supplier_index` (input order) before any computation.
- **Rationale**: `Send` gives parallel per-supplier isolation (FR-009) — each branch state contains
  only its own PDF bytes. `operator.add` is safe for concurrent writes; the explicit sort removes
  completion-order nondeterminism (Principle II).
- **Alternatives**: Python `ThreadPoolExecutor` loop inside one node — loses graph visibility and
  per-supplier streaming events.

## R4. Progress streaming to Streamlit

- **Decision**: `for ns, chunk in graph.stream(inputs, config, stream_mode="updates",
  subgraphs=True)`; the UI maps `(namespace, node_name)` to per-supplier status
  (waiting → extracting → evaluating → retrying → done/flagged/failed). Each subgraph node also
  writes a `progress` event `{supplier_index, stage}`. No checkpointer is used (state containing PDF
  bytes is never persisted — FR-035).
- **Rationale**: Keeps UI logic-free; one generator drives both progress and final state.

## R5. Exact-tie comparison for PPI

- **Decision**: Scores are stored as floats, but the ranking key uses `fractions.Fraction` built
  from `Fraction(str(score))`, weights (ints), and max scores, so mathematically equal PPIs compare
  equal (spec edge case "numerically equal values"). Floats (full precision) are what get stored
  and exported.
- **Alternatives**: `round(ppi, 9)` — arbitrary epsilon; `Decimal` — also fine but Fraction is exact
  for division.

## R6. Zero benchmark

- **Decision**: If benchmark == 0, relative % = 0 for all suppliers on that criterion, one
  `zero_benchmark` warning (supplier = None), weight still in PPI denominator (FR-023/024).

## R7. PDF extraction & intake checks

- **Decision**: PyMuPDF `fitz.open(stream=bytes, filetype="pdf")`. Reject: magic bytes not `%PDF`,
  > 10 MB, `doc.needs_pass`, open error, < 200 non-whitespace chars. Warn: pages with no text.
  Duplicate files via SHA-256 of bytes; duplicate names via
  `" ".join(name.split()).casefold()`. Truncation: text capped at 60 000 chars (≈15k tokens) with a
  `document_truncated` warning.
- **Rationale**: All checks run in `tools/intake.py` before the graph; Evaluate disabled until clean.

## R8. Evidence grounding

- **Decision**: Normalize both texts with `" ".join(s.split()).casefold()`; strip surrounding
  quotes/ellipses from evidence; if the normalized evidence is not a substring of the normalized
  document text → `evidence_not_found` warning (score kept). Done in `validate` while the text is
  still in subgraph state; text dropped afterwards.

## R9. SQLite on Community Cloud

- **Decision**: `init_db(path)` runs `CREATE TABLE IF NOT EXISTS` + `INSERT OR IGNORE` seed of the
  5 default criteria; called once per process via `st.cache_resource` wrapper in `app.py` that only
  returns the DB path (no run data cached). At start, `UPDATE rfp_runs SET status='FAILED',
  failure_reason='interrupted' WHERE status='RUNNING'`. New connection per operation
  (`check_same_thread` safe across graph threads).

## R10. Secrets

- **Decision**: `config.get_api_key()` reads `st.secrets["OPENAI_API_KEY"]` (if available) else
  `os.environ`. Missing → `evaluate` disabled with configuration message (FR-036).
  `.streamlit/secrets.toml.example` committed with a placeholder.

## R11. Synthetic PDFs

- **Decision**: `scripts/make_synthetic_pdfs.py` uses reportlab `SimpleDocTemplate` + `Paragraph`
  + `Table` to write 4 fictional 2–4-page proposals with all six required sections and the
  profiles from User Story 6. Output committed to `data/samples/`.
