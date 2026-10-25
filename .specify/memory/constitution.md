<!--
SYNC IMPACT REPORT
==================
Version change: (unratified template) → 1.0.0
Bump rationale: Initial ratification; all placeholders replaced with project governance.

Modified principles (template placeholder → new title):
  - [PRINCIPLE_1_NAME] → I. LLM Judges, Python Decides
  - [PRINCIPLE_2_NAME] → II. Determinism
  - [PRINCIPLE_3_NAME] → III. Evidence-Grounded & Traceable
  - [PRINCIPLE_4_NAME] → IV. Untrusted LLM Output
  - [PRINCIPLE_5_NAME] → V. LangGraph Orchestration
Added principles (beyond the template's five slots):
  - VI. Configuration as Data
  - VII. Test-First Business Rules (NON-NEGOTIABLE)

Added sections:
  - Technology & Data Constraints   (was [SECTION_2_NAME])
  - Development Workflow & Quality Gates   (was [SECTION_3_NAME])
  - Governance (filled from [GOVERNANCE_RULES])
Removed sections: none

Dependent templates (read the constitution at runtime; not modified by this command):
  - .specify/templates/plan-template.md    ✅ compatible — "Constitution Check" and
    "Complexity Tracking" sections already exist and match Governance requirements
  - .specify/templates/spec-template.md    ✅ compatible — no change required
  - .specify/templates/tasks-template.md   ✅ compatible — Principle VII requires test tasks
    for business rules to precede implementation tasks
  - .specify/templates/checklist-template.md ✅ compatible — no change required

Follow-up TODOs: none. Ratification date set to the date of first adoption (2026-10-25).
-->

# Agentic RFP Evaluation Constitution

## Core Principles

### I. LLM Judges, Python Decides

The LLM's role is strictly limited to judging proposal content. For each supplier it MAY produce
only: per-criterion scores, justifications, supporting evidence, risks, and an overall summary.

- All arithmetic — absolute weighted scores, criterion benchmarks, criterion gaps, relative
  performance percentages, the Peer Performance Index (PPI), tie-breaks, and final ranks — MUST
  be computed by deterministic Python code.
- No LLM call is permitted after the validation step. Scoring, benchmarking, ranking,
  persistence, and presentation MUST NOT invoke an LLM.
- The LLM MUST NOT be asked to compare suppliers, compute totals, or suggest a ranking.

**Rationale**: Procurement decisions must be auditable and reproducible. LLMs are useful for
reading and judging unstructured text, but are unreliable at arithmetic and non-deterministic
in ordering; isolating them to judgment keeps every decision rule inspectable in code.

### II. Determinism

Identical validated scorecards (plus identical supplier metadata and criteria) MUST always
produce identical scores, PPIs, and ordering.

- Ranking MUST use a stable sort with the mandated tie-break key, in this order:
  1) higher PPI, 2) earlier submission date, 3) higher historical experience rating,
  4) supplier name ascending. Ranks 1, 2, 3, … are assigned only after this sort.
- The input order to the sort MUST itself be deterministic (never dependent on dict/set
  iteration order of unordered sources, thread completion order, or wall-clock time).
- LLM calls MUST use temperature 0 (and any other determinism controls the provider offers).
- Computed values MUST be stored and compared at full precision. Rounding is applied only at
  display time (UI and human-readable exports), never before comparison or persistence.

**Rationale**: The project's success condition is that the same validated inputs always yield
the same formulas and ordering. Non-determinism after validation is a defect, not variance.

### III. Evidence-Grounded & Traceable

- Every criterion score MUST cite evidence drawn only from that supplier's own document. A
  supplier's prompt MUST NOT contain text from any other supplier's document.
- Prompts MUST instruct the model to use only evidence present in the supplied document, to
  return one result for every active criterion, to stay within the score range, and to output
  JSON only.
- Validation SHOULD flag (as a warning) evidence that cannot be located in the source text.
- Every final number MUST be traceable to its criterion, weight, max score, supplier evidence,
  and the business rule (formula or tie-break step) that produced it.
- The complete result JSON for each run MUST be persisted, including: the criteria snapshot
  (ids, names, weights, max scores) used for that run, raw-validated scorecards, all computed
  metrics, all validation warnings, and the tie-break explanation. It MUST be downloadable.

**Rationale**: An evaluator, auditor, or losing supplier must be able to reconstruct exactly
why a supplier received its score and rank, even after criteria are later changed.

### IV. Untrusted LLM Output

LLM output is untrusted input and MUST be validated at the boundary with Pydantic models before
any downstream component consumes it.

- Malformed JSON, missing fields, unknown criterion ids, and wrong types MUST be handled
  without raising out of the run.
- Missing criteria MUST be filled with a defined default (documented in the feature spec).
- Out-of-range scores MUST be clipped to `[0, max_score]`.
- Every normalization or fix MUST record a structured warning (supplier, criterion, issue,
  original value, applied value) that is persisted with the run and shown in the UI.
- Bad LLM output, or a failed LLM call, MUST never crash a run. The affected supplier is
  completed with a normalized scorecard and warnings, or explicitly marked failed with a
  reason; the remaining suppliers still complete.

**Rationale**: Models occasionally return invalid or partial JSON. A robust evaluation degrades
gracefully and visibly rather than failing silently or aborting the whole batch.

### V. LangGraph Orchestration

- A single parent LangGraph graph orchestrates the end-to-end run (setup → evaluate → validate
  → score → benchmark → rank → persist).
- Per-supplier evaluation (extract text → build prompt → call LLM → validate) MUST run as a
  subgraph invoked once per supplier.
- Components (document tool, evaluation agent, validation tool, ranking tool, persistence)
  MUST communicate only through typed shared state (TypedDict or Pydantic schemas).
- Any state key written by parallel branches MUST declare a reducer; the reducer's result MUST
  be order-independent or followed by a deterministic sort (see Principle II).
- No global mutable state: no module-level caches, singletons, or globals that carry
  run-specific data. Configuration and clients are passed in or constructed per run.

**Rationale**: Explicit graph structure makes the agentic workflow inspectable and testable
node by node; typed state and reducers prevent hidden coupling and race conditions when
suppliers are evaluated in parallel.

### VI. Configuration as Data

- Evaluation criteria (id, name, description, weight, max score, active flag) MUST live in
  SQLite, not in code or prompt strings.
- Prompts MUST be built dynamically from the currently active criteria; adding, removing,
  or reweighting a criterion MUST require no code change.
- Active criteria weights MUST total exactly 100. A run MUST NOT start if they do not; the UI
  MUST show a clear validation message instead.
- Each run MUST take a single snapshot of active criteria at its start and use that snapshot
  for prompting, validation, scoring, and persistence throughout the run.

**Rationale**: Procurement teams tune criteria per RFP. Treating criteria as data keeps
behavior configurable without redeploys, while the per-run snapshot keeps each run consistent.

### VII. Test-First Business Rules (NON-NEGOTIABLE)

- Unit tests for business rules MUST be written, and observed failing, before the
  implementation they cover. This includes at minimum:
  - absolute weighted score, benchmark, gap, relative %, and PPI formulas;
  - zero-benchmark handling (no division error, no NaN, documented defined result);
  - every tie-break level, including full ties resolved by supplier name;
  - validation/normalization: missing criteria, out-of-range clipping, malformed JSON,
    unknown criterion ids, and the warnings each produces;
  - active-weights-total-100 enforcement.
- Business-rule tests MUST be deterministic and MUST NOT call a real LLM or network; LLM
  responses are supplied as fixtures or stubs.

**Rationale**: Scoring and ranking rules are the product's correctness contract. Writing the
tests first pins down edge cases (such as a zero benchmark) before code can paper over them.

## Technology & Data Constraints

- **Language**: Python 3.11 or newer.
- **UI**: Streamlit.
- **Persistence**: SQLite (via the standard library `sqlite3` or a thin wrapper). Schema
  creation and criteria seeding MUST be idempotent and runnable at app startup, because the
  Streamlit Community Cloud filesystem is ephemeral.
- **Orchestration**: LangGraph (see Principle V); validation with Pydantic (see Principle IV).
- **Data**: Synthetic data only. Supplier PDFs, names, prices, and references MUST be
  fictional. Real or confidential supplier data MUST NOT be committed or used.
- **Secrets**: API keys MUST be read from environment variables or `st.secrets` and MUST NEVER
  be committed. `.env` and `.streamlit/secrets.toml` MUST be listed in `.gitignore`; a
  `secrets.toml.example` (with placeholder values) MAY be committed.
- **Deployment**: The application MUST deploy and run on Streamlit Community Cloud from the
  repository with a `requirements.txt` and no system packages or services beyond what that
  platform provides.

## Development Workflow & Quality Gates

- **Spec-driven flow**: Features follow specify → (clarify) → plan → tasks → implement.
- **Constitution Check gate**: Every `plan.md` MUST include a Constitution Check that evaluates
  the design against each of Principles I–VII and the constraints above. The check is run
  before Phase 0 research and re-run after Phase 1 design. A plan that fails the check MUST NOT
  proceed to tasks unless each violation is justified in Complexity Tracking.
- **Task ordering**: In `tasks.md`, test tasks for business rules (Principle VII) MUST precede
  the implementation tasks they cover.
- **Merge gate**: All unit tests MUST pass before code is merged or deployed. The test suite
  MUST run without network access or API keys.
- **Secret hygiene**: Before each commit, changes MUST be checked to ensure no API keys or
  secrets files are staged.

## Governance

- This constitution supersedes all other project practices, conventions, and guidance. Where a
  spec, plan, or task conflicts with it, the constitution wins until it is formally amended.
- **Compliance review**: Every plan MUST pass the Constitution Check described above. Code
  review and `/speckit-analyze` runs MUST treat constitution violations as blocking.
- **Deviations**: Any deviation from a principle or constraint MUST be recorded in the plan's
  Complexity Tracking table with the specific violation, why it is needed, and why the simpler
  compliant alternative was rejected. Unjustified deviations are not permitted.
- **Amendments**: Changes to this document are made via `/speckit-constitution`, MUST include
  a Sync Impact Report, and MUST update the version and Last Amended date below. Dependent
  specs and plans affected by an amendment MUST be re-checked.
- **Versioning policy** (semantic versioning):
  - MAJOR — a principle or governance rule is removed or redefined incompatibly.
  - MINOR — a new principle or section is added, or guidance is materially expanded.
  - PATCH — clarifications, wording, or typo fixes with no change in meaning.

**Version**: 1.0.0 | **Ratified**: 2026-10-25 | **Last Amended**: 2026-10-25
