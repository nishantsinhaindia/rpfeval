# Data Model: Agentic RFP Evaluation and Supplier Ranking

Pydantic v2 models live in `rfp_eval/schemas/`; graph states in `rfp_eval/graph/state.py`
(see [contracts/graph-state.md](contracts/graph-state.md)).

## Entities

### Criterion (`schemas/criteria.py`)
| Field | Type | Rules |
|---|---|---|
| criterion_id | int | PK, stable |
| name | str | non-empty |
| description | str | what the LLM should inspect |
| weight | int | 0–100 |
| max_score | float | > 0 (seed 10) |
| is_active | bool | |

`CriteriaSnapshot = tuple[Criterion, ...]` — active criteria only, ordered by `criterion_id`,
frozen (`model_config = ConfigDict(frozen=True)`). Validation: `sum(weight) == 100` else
`WeightTotalError(total)` (FR-003); empty → total 0 → blocked.

### SupplierInput (`schemas/supplier.py`)
| Field | Type | Rules |
|---|---|---|
| supplier_index | int | input order, used for deterministic re-sort |
| supplier_name | str | trimmed, inner spaces collapsed, non-empty, unique by casefold |
| submission_date | date | ≤ today |
| experience_rating | int | 1–5 |
| file_name | str | |
| file_sha256 | str | unique per run |
| pdf_bytes | bytes | transient — excluded from persistence (`Field(exclude=True)`) |

### LLM output (`schemas/llm.py`) — lenient parse of untrusted JSON
`RawLLMEvaluation`: `supplier_name: str | None`, `criteria: list[RawCriterionJudgement]`,
`risks: list[str] = []`, `overall_summary: str = ""`; `extra="ignore"`.
`RawCriterionJudgement`: `criterion_id: Any`, `score: Any`, `justification: Any`, `evidence: Any`.
Strictness is applied by `tools/validation.py`, not by the model, so every defect can be warned.

### AttemptRecord (`schemas/scorecard.py`)
`attempt: int (1|2)`, `raw_response: str | None`, `failure_reason: str | None`,
`used_for_normalization: bool`.

### CriterionResult (`schemas/scorecard.py`)
| Field | Type | Set by |
|---|---|---|
| criterion_id, name, weight, max_score | from snapshot | normalize |
| score | float | normalize (0..max) |
| justification | str | normalize |
| evidence | str | normalize; `"no evidence found"` if empty |
| flags | list[Literal["not_assessed","no_evidence_found","clipped","evidence_not_found"]] | normalize |
| benchmark, gap, relative_pct, weighted_contribution | float \| None | scoring |

### Scorecard
`supplier_index`, `supplier_name`, `submission_date`, `experience_rating`,
`criteria: list[CriterionResult]` (one per snapshot criterion, snapshot order),
`risks: list[str]`, `overall_summary: str`, `evaluation_failed: bool`,
`attempts: list[AttemptRecord]`.

### Warning (`schemas/warnings.py`)
`supplier_name: str | None`, `criterion_id: int | None`, `issue: IssueType`,
`original_value: str | None`, `applied_value: str | None`, `message: str`.
`IssueType` ∈ {`retry`, `busy_retry`, `call_failed`, `malformed_output`, `extra_text`,
`missing_criterion`, `non_numeric_score`, `numeric_text_converted`, `clipped`,
`unknown_criterion`, `duplicate_criterion`, `supplier_name_mismatch`, `no_evidence`,
`evidence_not_found`, `zero_benchmark`, `document_truncated`, `pages_without_text`,
`extraction_failed`, `evaluation_failed`}.

### RankedSupplier / RunResult (`schemas/results.py`)
`RankedSupplier`: scorecard + `absolute_score: float`, `ppi: float`, `rank: int`,
`tie_break_rule: Literal["ppi","submission_date","experience_rating","supplier_name"] | None`.
`RunResult`: `rfp_run_id`, `created_at`, `status`, `failure_reason`, `criteria_snapshot`,
`suppliers: list[RankedSupplier]` (rank order), `warnings: list[Warning]`,
`tie_break_explanation: list[str]`. Serialized with `model_dump(mode="json")` — full precision.

## Formulas (pure, `rfp_eval/scoring`)

- `absolute_score = Σ (score / max_score) × weight`
- `benchmark[c] = max(score[s][c] for s)`
- `gap = score − benchmark`
- `relative_pct = score / benchmark × 100`, or `0` (+1 warning) when benchmark = 0
- `ppi = Σ(weight × relative_pct) / Σ weight` (all snapshot criteria)
- `weighted_contribution = (score / max_score) × weight`
- sort key: `(-ppi_exact, submission_date, -experience_rating, supplier_name.casefold())`, stable;
  ranks 1..N

## SQLite schema (`rfp_eval/db/schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS evaluation_criteria (
  criterion_id INTEGER PRIMARY KEY,
  name         TEXT    NOT NULL UNIQUE,
  description  TEXT    NOT NULL,
  weight       INTEGER NOT NULL CHECK (weight BETWEEN 0 AND 100),
  max_score    REAL    NOT NULL CHECK (max_score > 0),
  is_active    INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);
CREATE TABLE IF NOT EXISTS rfp_runs (
  rfp_run_id      TEXT PRIMARY KEY,           -- uuid4 hex
  created_at      TEXT NOT NULL,              -- ISO-8601 UTC
  status          TEXT NOT NULL CHECK (status IN ('RUNNING','COMPLETED','FAILED')),
  failure_reason  TEXT,
  criteria_json   TEXT NOT NULL,              -- snapshot
  result_json     TEXT                        -- full RunResult when finished
);
CREATE TABLE IF NOT EXISTS supplier_results (
  rfp_run_id        TEXT NOT NULL REFERENCES rfp_runs(rfp_run_id),
  supplier_name     TEXT NOT NULL,
  submission_date   TEXT NOT NULL,
  experience_rating INTEGER NOT NULL,
  absolute_score    REAL NOT NULL,
  ppi               REAL NOT NULL,
  final_rank        INTEGER NOT NULL,
  result_json       TEXT NOT NULL,            -- RankedSupplier incl. raw attempts
  PRIMARY KEY (rfp_run_id, supplier_name)
);
```

Seed (`INSERT OR IGNORE`): 1 Technical Capability 30, 2 Implementation Plan 20,
3 Commercial Value 20, 4 Security & Compliance 20, 5 Support & Experience 10; all max 10, active.

## State transitions

```text
rfp_runs.status:  (none) --create_run--> RUNNING --persist ok--> COMPLETED
                                         RUNNING --all suppliers failed / persist error--> FAILED
                                         RUNNING --found at app start--> FAILED ("interrupted")

supplier (subgraph): waiting → extracting → evaluating(attempt 1) → [retrying(attempt 2)]
                     → done | flagged (warnings) | failed (evaluation_failed zero scorecard)
```
