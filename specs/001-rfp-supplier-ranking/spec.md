# Feature Specification: Agentic RFP Evaluation and Supplier Ranking

**Feature Branch**: `001-rfp-supplier-ranking` (no git repository yet; branch not created)

**Created**: 2026-10-25

**Status**: Draft

**Input**: User description: "Build 'Agentic RFP Evaluation and Supplier Ranking': a procurement
evaluator uploads several supplier RFP response PDFs; the system scores each proposal against
configurable criteria using AI, benchmarks suppliers against each other, and shows an explainable
leaderboard." The user stories (P1–P3), exact business rules, and NFR-01 to NFR-10 supplied with
this description are incorporated below.

## Clarifications

### Session 2026-10-25

- Q: The AI gives a non-zero score but no evidence for a criterion — what happens to the score?
  → A: Keep the AI's score; mark "no evidence found" and record a warning (FR-018).
- Q: A supplier gets no usable AI response even after the retry — how does it appear in results?
  → A: Rank it with every criterion 0 "not assessed", included in benchmarks and ranking, and
  flagged "evaluation failed" (FR-019).
- Q: Should anyone with the public link be able to run evaluations and edit criteria, or should
  those actions require a shared access code? → A: Fully open — no access code; the AI-cost and
  criteria-tampering risk is accepted for this synthetic-data demo.
- Q: How long should the system wait for a single AI response before treating that attempt as
  failed and moving to the retry? → A: 90 seconds per attempt; the 3-minute run target applies to
  runs where no retry is needed.
- Q: Should each run's stored result also keep the AI's original, unmodified responses (both
  attempts, if retried) alongside the cleaned-up scorecard? → A: Yes — store them, show them in run
  details, and include them in the JSON download.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Evaluate a batch of supplier proposals (Priority: P1)

A procurement evaluator opens the application and sees the active evaluation criteria (name,
description, weight, maximum score). They upload two or more supplier proposal PDFs and, for each
one, enter the supplier name, submission date, and historical experience rating (1–5). They click
Evaluate. The system creates one RFP run ID, reloads the active criteria, evaluates every supplier
while showing per-supplier progress, and then shows a leaderboard with rank, supplier, absolute
score, PPI, submission date, and experience rating.

**Why this priority**: This is the core value of the product — replacing slow, inconsistent manual
reading of proposals with a consistent, ranked comparison. Without it nothing else matters.

**Independent Test**: Upload the four sample proposals with valid metadata, click Evaluate, and
confirm a leaderboard of four ranked suppliers appears under a single new run ID.

**Acceptance Scenarios**:

1. **Given** active criteria whose weights total 100, **When** the user opens the application,
   **Then** each active criterion is listed with its name, description, weight, and maximum score,
   along with the weight total.
2. **Given** two or more valid PDFs each with valid supplier metadata, **When** the user clicks
   Evaluate, **Then** exactly one new RFP run ID is created and every supplier is evaluated against
   the criteria as they were at the moment Evaluate was clicked.
3. **Given** a run in progress, **When** suppliers are being evaluated, **Then** the user sees the
   progress state of each supplier individually (e.g., waiting, evaluating, done, flagged).
4. **Given** a completed run, **When** the leaderboard is shown, **Then** each supplier appears once
   with a unique sequential rank (1..N), supplier name, absolute score, PPI, submission date, and
   experience rating, ordered by rank.
5. **Given** only one PDF has been uploaded, **When** the user tries to evaluate, **Then** evaluation
   is blocked with a message stating that at least two supplier proposals are required.

---

### User Story 2 - Explain and export results (Priority: P1)

After a run, the evaluator opens any supplier's detailed scorecard to see, per criterion, the score,
benchmark, gap, relative %, weight, supporting evidence, and justification. A run-details view shows
the RFP run ID, every warning raised during the run, and a plain-language explanation of how ties
were broken. The evaluator downloads the complete result as a JSON file to share or archive.

**Why this priority**: A ranking that cannot be explained cannot be defended to stakeholders or
suppliers. Explainability is as essential as the ranking itself.

**Independent Test**: Using a completed run (or stored validated scorecards), open each supplier's
scorecard, recompute one supplier's absolute score and PPI by hand from the displayed values, and
confirm they match; download the JSON and confirm it contains the same values and the criteria
snapshot.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** the user opens a supplier's scorecard, **Then** each criterion
   shows score, maximum score, benchmark, gap, relative %, weight, weighted contribution, evidence,
   justification, and any status flag (e.g., "not assessed", "no evidence found", "clipped").
2. **Given** a completed run, **When** the user opens run details, **Then** the run ID, run status,
   criteria snapshot, all warnings (grouped by supplier), and the tie-break explanation are shown.
3. **Given** two suppliers with equal PPI, **When** the user reads the tie-break explanation,
   **Then** it states in plain language which rule decided their order and the values compared
   (e.g., "NexaWorks ranks above Orbit Digital: equal PPI 82.50; earlier submission date
   2026-03-01 vs 2026-03-04").
4. **Given** a completed run, **When** the user downloads the result, **Then** the file contains the
   run ID, status, criteria snapshot, each supplier's metadata, raw AI responses, validated
   scorecard, peer metrics, absolute score, PPI, rank, risks, summary, all warnings, and the
   tie-break explanation, at full precision.

---

### User Story 3 - Resilient handling of bad AI output (Priority: P2)

If the AI returns malformed output, omits criteria, or gives non-numeric or out-of-range scores, the
system retries the evaluation once. If problems remain, it normalizes the result (missing or
non-numeric → 0 marked "not assessed"; out-of-range → clipped to 0..maximum score), records one
warning per fix, and the run still completes.

**Why this priority**: AI output is occasionally invalid. Without this, one bad response could crash
or silently corrupt a run, undermining trust in every result.

**Independent Test**: Substitute canned AI responses containing each defect (malformed output,
missing criterion, non-numeric score, score above maximum, negative score) and confirm the run
completes, the defects are normalized as specified, and one warning is recorded per fix.

**Acceptance Scenarios**:

1. **Given** the first AI response for a supplier is malformed, **When** the system processes it,
   **Then** it retries once, and if the retry is valid uses it with a warning noting the retry.
2. **Given** a response that omits one active criterion after the retry, **When** normalized,
   **Then** that criterion receives score 0 marked "not assessed" and one warning is recorded.
3. **Given** a response with a score of 12 on a criterion with maximum 10, **When** normalized,
   **Then** the score becomes 10 and a warning records the original (12) and applied (10) values.
4. **Given** a response with a score of "eight" (non-numeric), **When** normalized, **Then** the score
   becomes 0 marked "not assessed" with a warning.
5. **Given** the AI service fails or returns unusable output for one supplier on both attempts,
   **When** the run continues, **Then** the other suppliers are still evaluated, and the failed
   supplier is ranked with every criterion scored 0 "not assessed" and flagged "evaluation failed"
   with warnings.
6. **Given** the AI scores a criterion 7 out of 10 but gives no evidence, **When** validated,
   **Then** the score stays 7, the evidence reads "no evidence found", and a warning is recorded.

---

### User Story 4 - Manage evaluation criteria (Priority: P2)

The evaluator activates or deactivates criteria and edits their weights from within the application
without any code changes. The application shows the running total of active weights. If active
weights do not total 100, evaluation is blocked with a clear message.

**Why this priority**: Different RFPs emphasize different qualities. Configurable criteria let the
same tool serve many procurements without developer involvement.

**Independent Test**: Deactivate one criterion, adjust the remaining weights to total 100, run an
evaluation, and confirm the evaluation and results use only the active criteria with the new
weights; then make the total 95 and confirm Evaluate is blocked.

**Acceptance Scenarios**:

1. **Given** the criteria list, **When** the user deactivates a criterion and saves, **Then** it no
   longer appears among active criteria and is not used in subsequent runs.
2. **Given** active weights totalling 95, **When** the user tries to evaluate, **Then** evaluation is
   blocked with a message stating the current total (95) and that it must equal 100.
3. **Given** a past run, **When** the user later changes criteria, **Then** the past run's displayed
   results and criteria snapshot are unchanged.

---

### User Story 5 - Reopen past runs (Priority: P3)

The evaluator sees a list of past runs (run ID, date and time, status, number of suppliers, top-ranked
supplier) and reopens any one to see its leaderboard, scorecards, run details, and JSON download
exactly as they were when the run finished.

**Why this priority**: Useful for revisiting and comparing decisions, but the core workflow delivers
value without it.

**Independent Test**: Complete two runs, open the run history, reopen the first run, and confirm its
leaderboard and scorecards match those shown when it completed.

**Acceptance Scenarios**:

1. **Given** at least one stored run, **When** the user opens run history, **Then** each run is listed
   with run ID, date and time, status, supplier count, and top-ranked supplier, newest first.
2. **Given** a stored completed run, **When** the user reopens it, **Then** the leaderboard,
   scorecards, warnings, tie-break explanation, and JSON download match the original results and
   use the run's own criteria snapshot.

---

### User Story 6 - Synthetic sample proposals (Priority: P3)

The evaluator (and anyone reviewing the project) has four fictional supplier proposals, each 2–4
pages, to demonstrate the system: Apex Systems, BrightPath Tech, NexaWorks, and Orbit Digital. Each
has deliberately different strengths, weaknesses, prices, schedules, evidence quality, and gaps.

**Why this priority**: Required to demonstrate and test the system without real (confidential)
supplier data, but does not itself deliver evaluation capability.

**Independent Test**: Open each sample PDF and confirm it is 2–4 pages, contains every required
section, and matches its intended profile; run all four through the system.

**Acceptance Scenarios**:

1. **Given** the sample set, **When** each proposal is opened, **Then** it contains an executive
   summary and understanding of the requirement, proposed solution and implementation approach,
   timeline/team structure/milestones, price table with assumptions, security/compliance/risk
   controls, and support model/relevant experience/references.
2. **Given** the sample set, **When** compared, **Then** profiles differ as follows: Apex Systems —
   strong technical design and security, higher price, moderate schedule; BrightPath Tech — lowest
   price and fast timeline, weak compliance detail and limited experience; NexaWorks — balanced,
   strongest implementation plan and support model; Orbit Digital — strong experience and
   references, vague integration plan, medium pricing.

---

### Edge Cases

- **Zero benchmark**: every supplier scores 0 on a criterion → relative % is 0 for all suppliers on
  that criterion, one warning is recorded for that criterion, and the criterion's weight still
  counts in the PPI denominator.
- **Shared benchmark**: two or more suppliers share the highest score on a criterion → each has
  gap 0 and relative % 100 on that criterion.
- **Ties at every tie-break level**: equal PPI → earlier submission date wins; equal PPI and date →
  higher experience rating wins; equal PPI, date, and rating → supplier name A–Z decides. Ranks are
  always unique and sequential.
- **Numerically equal values**: two PPIs that are mathematically equal (e.g., produced from different
  but equivalent score combinations) are treated as a tie, never ordered by numeric rounding noise.
- **All criteria deactivated** → active weight total is 0 → evaluation blocked.
- **Criteria changed during or after a run** → the run keeps using, and displaying, its own snapshot.
- **Duplicate supplier names** differing only by letter case or surrounding spaces (e.g., "Apex
  Systems" and "apex systems ") → blocked as duplicates.
- **Invalid files**: a non-PDF file renamed to `.pdf`, a file over 10 MB, a password-protected PDF,
  or an image-only (scanned) PDF with no extractable text → rejected before evaluation with a
  message naming the file and the reason.
- **Submission date of today** → accepted; **tomorrow or later** → rejected.
- **Very long document** whose text exceeds what can be evaluated in one request → the leading
  portion is evaluated and a "document truncated" warning is recorded for that supplier.
- **AI output wrapped in extra text** (e.g., commentary around the result) → the result is extracted
  if exactly one result object is present, with a warning; otherwise treated as malformed.
- **AI output with unknown criterion IDs** → ignored with a warning; **duplicate criterion IDs** → the
  first occurrence is kept and the rest ignored with a warning.
- **AI output naming a different supplier** → ignored; the user-entered supplier name is always used.
- **Score with no evidence**: the AI gives a non-zero score but no evidence → the score is kept,
  marked "no evidence found", and a warning is recorded (FR-018).
- **One supplier's AI evaluation fails twice** → that supplier is ranked with all criteria 0
  "not assessed" (normally last) and flagged "evaluation failed" (FR-019).
- **Evidence not found in the document**: quoted evidence cannot be located in that supplier's own
  text → the criterion is flagged with a warning.
- **Slow AI response**: an attempt that receives no response within 90 seconds is treated as a
  failed call and retried once (FR-014).
- **AI service fails for every supplier** → no leaderboard is produced and the run is marked FAILED
  with the reason shown.
- **Browser session closed or application restarted mid-run** → the run is marked FAILED
  ("interrupted") the next time the application starts; it is never left RUNNING indefinitely.
- **AI service credentials missing** → evaluation is blocked with a configuration message; criteria
  management and run history remain usable.

## Requirements *(mandatory)*

### Functional Requirements

**Criteria configuration**

- **FR-001**: System MUST display all active evaluation criteria with name, description, weight, and
  maximum score, plus the total of active weights.
- **FR-002**: Users MUST be able to activate and deactivate criteria and edit criteria weights from
  within the application, with changes saved persistently and requiring no code change.
- **FR-003**: System MUST block evaluation when active weights do not total exactly 100, showing the
  current total and that it must equal 100. Criteria changes MAY be saved while the total is not 100
  so users can adjust weights step by step.
- **FR-004**: System MUST create its data store and seed the default criteria automatically on first
  start, with no manual setup step (NFR-09).

**Input and validation**

- **FR-005**: Users MUST be able to upload between 2 and 10 supplier proposal files in a single run.
- **FR-006**: For each uploaded file, users MUST enter a supplier name, a submission date, and a
  historical experience rating; the supplier name MAY be pre-filled from the file name and edited.
- **FR-007**: System MUST reject, before any evaluation starts and with a specific message naming
  the affected file or supplier (NFR-06):
  - files that are not PDFs;
  - files larger than 10 MB;
  - PDFs with no extractable text (including password-protected and image-only files);
  - missing or blank supplier names;
  - supplier names that duplicate another in the same run (compared case-insensitively, ignoring
    leading/trailing spaces);
  - submission dates later than today;
  - experience ratings that are not whole numbers from 1 to 5.

**Run orchestration**

- **FR-008**: On Evaluate, the system MUST create exactly one unique RFP run ID, set the run status
  to RUNNING, reload the active criteria, and take a criteria snapshot that is used for prompting,
  validation, scoring, display, and storage for the whole run.
- **FR-009**: System MUST evaluate each supplier independently; the AI evaluation for a supplier MUST
  receive only that supplier's document text and the run's criteria snapshot — never content from
  another supplier's document.
- **FR-010**: The AI evaluation MUST return, for every criterion in the snapshot, a score, a
  justification, and supporting evidence, plus a list of identified risks and an overall summary.
  The AI MUST NOT compute or be asked for totals, benchmarks, gaps, relative %, PPI, tie-breaks, or
  ranks.
- **FR-011**: System MUST show per-supplier progress while a run is in progress (NFR-05).
- **FR-012**: A failure affecting one supplier (unreadable document or failed AI response) MUST NOT
  abort the run; that supplier is flagged with warnings and the remaining suppliers continue
  (NFR-04).
- **FR-013**: Run status MUST be one of RUNNING, COMPLETED, or FAILED:
  - COMPLETED when all suppliers have been processed and results stored, even if warnings exist;
  - FAILED when no leaderboard can be produced (e.g., no supplier received a usable AI response,
    or results could not be stored), with the reason recorded and shown;
  - a run found still RUNNING when the application starts is set to FAILED ("interrupted").

**AI output validation and normalization**

- **FR-014**: System MUST treat AI output as untrusted. When a response is malformed, omits any
  snapshot criterion, contains a non-numeric score, contains an out-of-range score, or the AI call
  itself fails, the system MUST retry that supplier's evaluation exactly once. An attempt with no
  response within 90 seconds MUST be treated as a failed call.
- **FR-015**: After the retry, the system MUST normalize the most recent usable response as follows,
  never crashing the run:
  - missing criterion → score 0, marked "not assessed";
  - non-numeric score → score 0, marked "not assessed";
  - numeric value given as text (e.g., "8") → converted to the number;
  - score below 0 or above the criterion's maximum → clipped to 0 or the maximum, marked "clipped";
  - unknown criterion ID → ignored;
  - duplicate criterion ID → first occurrence kept, others ignored.
- **FR-016**: System MUST record one warning for every retry and every normalization fix, stating
  the supplier, criterion (if applicable), issue, original value, and applied value. Warnings MUST
  be stored with the run and shown in run details.
- **FR-017**: A criterion with no supporting evidence MUST be marked "no evidence found" (NFR-03).
  Evidence that cannot be located in that supplier's own document text MUST be flagged with a
  warning.
- **FR-018**: When the AI gives a non-zero score but no supporting evidence for a criterion, the
  system MUST keep the AI's score unchanged, set the evidence to "no evidence found", flag the
  criterion "no evidence found", and record a warning stating the unsupported score.
- **FR-019**: When a supplier receives no usable AI response after the retry, the system MUST score
  every criterion for that supplier 0 marked "not assessed", include the supplier in benchmarks and
  ranking like any other supplier, flag it as "evaluation failed" with warnings, and continue the
  run. If no supplier in the run receives a usable response, the run is FAILED (FR-013).

**Scoring and ranking (deterministic system rules — never performed by the AI)**

- **FR-020**: Absolute score for a supplier MUST equal the sum over snapshot criteria of
  (score ÷ maximum score) × weight. (Range 0–100.)
- **FR-021**: Benchmark for a criterion MUST equal the highest validated score for that criterion
  among the suppliers in the run.
- **FR-022**: Gap for a supplier on a criterion MUST equal supplier score − benchmark (0 for the
  benchmark leader or leaders, otherwise negative).
- **FR-023**: Relative % for a supplier on a criterion MUST equal (supplier score ÷ benchmark) × 100.
  If the benchmark is 0, relative % MUST be 0 for all suppliers on that criterion and one warning
  MUST be recorded for that criterion.
- **FR-024**: PPI for a supplier MUST equal sum(weight × relative %) ÷ sum(weight), summed over all
  criteria in the snapshot (zero-benchmark criteria included). (Range 0–100.)
- **FR-025**: Suppliers MUST be ranked by PPI descending, then earlier submission date, then higher
  experience rating, then supplier name A–Z (case-insensitive), using a stable sort; ranks are
  assigned 1..N sequentially after sorting, with no shared ranks.
- **FR-026**: Identical validated scorecards, supplier metadata, and criteria snapshot MUST always
  produce identical absolute scores, benchmarks, gaps, relative %, PPIs, and ranks (NFR-01).
  Values that are mathematically equal MUST compare as equal.
- **FR-027**: All computed values MUST be stored and compared at full precision; rounding (to 2
  decimal places) MUST be applied only when values are displayed.

**Results and explanation**

- **FR-028**: System MUST display a leaderboard with rank, supplier name, absolute score, PPI,
  submission date, and experience rating, plus a visible indicator for suppliers with warnings.
- **FR-029**: System MUST display, for each supplier, a scorecard with — per criterion — score,
  maximum score, benchmark, gap, relative %, weight, weighted contribution, evidence, justification,
  and status flags; and — per supplier — absolute score, PPI, rank, risks, and overall summary.
- **FR-030**: System MUST display run details: run ID, created date and time, status, criteria
  snapshot, all warnings grouped by supplier, the tie-break explanation, and each supplier's raw AI
  responses (FR-033a).
- **FR-031**: The tie-break explanation MUST, for every pair of adjacently ranked suppliers, state in
  plain language which rule decided their order (PPI, submission date, experience rating, or
  supplier name) and the values compared.
- **FR-032**: Users MUST be able to download the complete run result as a JSON file containing the
  run ID, created time, status, criteria snapshot, each supplier's metadata, validated scorecard
  (scores, justifications, evidence, flags), raw AI responses, peer metrics, absolute score, PPI,
  rank, risks, summary, all warnings, and the tie-break explanation, with numbers at full precision
  (NFR-02).

**Persistence and history**

- **FR-033**: System MUST store each run (run ID, created time, status) and, per supplier, the
  supplier name, submission date, experience rating, absolute score, PPI, final rank, and complete
  result, all under the run ID.
- **FR-033a**: For every AI attempt (first attempt and retry, if any), the system MUST store the
  AI's original, unmodified response exactly as received — or, for a failed call, the failure
  reason (e.g., "no response within 90 seconds") — as part of that supplier's result.
- **FR-034**: Users MUST be able to view a list of past runs (run ID, date and time, status, supplier
  count, top-ranked supplier), newest first, and reopen any run read-only to see its leaderboard,
  scorecards, run details, and JSON download as originally produced.
- **FR-035**: Uploaded PDF files and their full extracted text MUST NOT be retained after the run
  finishes; only results (including evidence excerpts and raw AI responses) are stored (NFR-07).

**Security and sample data**

- **FR-036**: AI service credentials MUST be supplied through deployment configuration and never
  stored in application source or the repository. If credentials are missing, evaluation MUST be
  blocked with a clear configuration message (NFR-07).
- **FR-037**: The project MUST include four fictional supplier proposal PDFs (Apex Systems,
  BrightPath Tech, NexaWorks, Orbit Digital), each 2–4 pages, containing the sections and profiles
  described in User Story 6. All names, prices, and references MUST be fictional.

### Key Entities *(include if feature involves data)*

- **Evaluation Criterion**: A configurable quality on which proposals are judged. Attributes: ID,
  name, description, weight (whole number 0–100), maximum score, active flag.
- **Criteria Snapshot**: An immutable copy of the active criteria taken when a run starts; belongs
  to exactly one run and is the sole criteria reference for that run forever after.
- **RFP Run**: One batch evaluation. Attributes: run ID, created date and time, status (RUNNING,
  COMPLETED, FAILED), failure reason (if any), criteria snapshot, run-level warnings, tie-break
  explanation.
- **Supplier Submission**: One supplier's entry in a run. Attributes: supplier name, submission
  date, experience rating, source file name. The document itself is transient and not retained.
- **Supplier Scorecard**: The validated AI judgment for one supplier. Contains one Criterion Result
  per snapshot criterion, plus risks and overall summary.
- **Criterion Result**: Score, justification, evidence, and status flags ("not assessed",
  "no evidence found", "clipped") for one supplier on one criterion (a supplier-level
  "evaluation failed" flag applies when no usable AI response was received); enriched with benchmark, gap,
  relative %, and weighted contribution after scoring.
- **AI Attempt Record**: One AI evaluation attempt for one supplier (first attempt or retry).
  Attributes: attempt number, raw response exactly as received or failure reason, and whether it
  was the response used for normalization.
- **Validation Warning**: A record of a retry, normalization fix, zero benchmark, truncation, or
  grounding issue. Attributes: supplier (if applicable), criterion (if applicable), issue type,
  original value, applied value, message.
- **Ranking Result**: Per supplier: absolute score, PPI, final rank, and the tie-break rule that
  separated it from the next-ranked supplier.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user, without instructions, completes a full run of the four sample
  proposals — from opening the application to viewing the leaderboard — in under 5 minutes (NFR-08).
- **SC-002**: A run of the four sample proposals (2–4 pages each) in which no AI retry is needed
  finishes within 3 minutes of clicking Evaluate, in each of 5 consecutive trial runs, with
  per-supplier progress visible throughout (NFR-05). Runs that need retries may take longer, since
  each AI attempt may wait up to 90 seconds.
- **SC-003**: Recomputing scores and ranking 100 times from the same stored validated scorecards
  yields identical absolute scores, PPIs, and ranks every time (100%) (NFR-01).
- **SC-004**: For a completed run, a reviewer can reproduce every displayed absolute score and PPI by
  hand using only the scorecard or downloaded JSON (criterion, weight, score, benchmark, and the
  stated rule), with 100% of values matching (NFR-02).
- **SC-005**: In a test set containing each AI-output defect (malformed output, missing criterion,
  non-numeric score, out-of-range score, failed call), 100% of runs complete without crashing and
  each fix produces exactly one warning.
- **SC-006**: 100% of invalid inputs listed in FR-007 are rejected before evaluation starts, each
  with a message that identifies the file or supplier and the reason (NFR-06).
- **SC-007**: For every scored criterion in a sample run, the quoted evidence is found in that
  supplier's own document (ignoring differences in spacing and letter case), or the criterion is
  flagged; no evidence is ever attributed from another supplier's document (NFR-03).
- **SC-008**: Automated checks cover every scoring and ranking rule, including a tie decided at each
  of the four tie-break levels and the zero-benchmark case, and all pass (NFR-10).
- **SC-009**: Opening a freshly deployed instance from its public URL shows the seeded criteria with
  no manual setup step (NFR-09).
- **SC-010**: After a run, no uploaded PDF is retained by the system, and a scan of the repository
  finds no AI service credentials (NFR-07).

## Assumptions

- **Users**: A single role — the procurement evaluator. There is no login, access code, or other
  access control; this is a classroom/demo application on a public URL using synthetic data only,
  so anyone with the URL can run evaluations, edit criteria, and view run history. The resulting
  AI-cost and criteria-tampering risk is explicitly accepted; the 10-supplier-per-run cap limits
  the cost of any single run.
- **Default criteria**: Seeded on first start as Technical Capability (30), Implementation Plan (20),
  Commercial Value (20), Security & Compliance (20), Support & Experience (10), each with a maximum
  score of 10.
- **Weights** are whole numbers from 0 to 100. **Scores** may be decimals between 0 and the
  criterion's maximum score.
- **Run size**: 2 to 10 suppliers per run; performance targets are defined for 4 suppliers.
- **Experience rating** is a whole number from 1 to 5. **Submission date** is a calendar date
  (no time); "the future" means later than the application's current date.
- **Supplier name** uniqueness and the A–Z tie-break are case-insensitive; names are trimmed of
  leading/trailing spaces.
- **Display** rounds values to 2 decimal places; stored and exported values keep full precision.
- **Text extraction** supports text-based PDFs only; scanned/image-only documents (which would need
  OCR) are out of scope and rejected.
- **AI service**: any AI model able to return structured results; credentials are configured by
  whoever deploys the app. The AI is used in its most repeatable (least random) setting.
- **Run history durability** is bounded by the hosting environment's storage; a platform reset or
  redeploy may clear history and the database is then recreated and re-seeded automatically. This is
  acceptable for a demo application.
- **Reopened runs** are read-only: no re-evaluation, score editing, or metadata changes.
- **Hosting**: the application is deployed to Streamlit Community Cloud, per the project
  constitution's constraints.
- **Out of scope**: authentication and user roles; manual override of AI scores; adding or deleting
  criteria or changing maximum scores (only activate/deactivate and edit weights); comparing results
  across runs; non-PDF formats; OCR.
