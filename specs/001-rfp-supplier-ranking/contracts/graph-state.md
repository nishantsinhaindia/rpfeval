# Contract: LangGraph states, entry point, and stream events

## Entry point (the only API `app.py` uses)

```python
from rfp_eval.graph.rfp_run_graph import build_rfp_run_graph
graph = build_rfp_run_graph()            # compiled, no checkpointer
config = {"configurable": {"db_path": DB_PATH, "llm": chat_model, "sleep": time.sleep}}
for namespace, update in graph.stream(
        {"suppliers": [SupplierInput, ...]}, config,
        stream_mode="updates", subgraphs=True):
    ...   # render progress / final state
```

Inputs: `suppliers` already passed `tools.intake.validate_batch()` (FR-005/007) and the criteria
weight check. `llm` is any LangChain `BaseChatModel` (tests pass a fake).

## RFPRunState (parent, `TypedDict`)

| Key | Type | Reducer | Written by |
|---|---|---|---|
| rfp_run_id | str | overwrite | create_run |
| criteria | CriteriaSnapshot | overwrite | load_criteria |
| suppliers | list[SupplierInput] | overwrite | input |
| scorecards | list[Scorecard] | `operator.add` (**shared with subgraph**) | supplier_eval |
| warnings | list[Warning] | `operator.add` (**shared with subgraph**) | supplier_eval, score, benchmark, rank |
| progress | list[ProgressEvent] | `operator.add` (**shared with subgraph**) | all nodes |
| benchmarks | dict[int, float] | overwrite | benchmark |
| leaderboard | list[RankedSupplier] | overwrite | rank |
| tie_break_explanation | list[str] | overwrite | rank |
| status | Literal["RUNNING","COMPLETED","FAILED"] | overwrite | create_run, persist, mark_failed |
| error | str \| None | overwrite | any node on fatal error |

## SupplierEvalState (subgraph, `TypedDict`)

| Key | Visibility | Type | Reducer |
|---|---|---|---|
| supplier | input (via Send) | SupplierInput | overwrite |
| criteria | input (via Send) | CriteriaSnapshot | overwrite |
| rfp_run_id | input (via Send) | str | overwrite |
| text | **private** | str | overwrite |
| messages | **private** | list[BaseMessage] | overwrite |
| raw_llm | **private** | list[AttemptRecord] | overwrite (node appends then returns full list) |
| attempts | **private** | int | overwrite |
| parsed | **private** | RawLLMEvaluation \| None | overwrite |
| needs_retry | **private** | bool | overwrite |
| scorecards | **shared → parent** | list[Scorecard] (len 1) | `operator.add` |
| warnings | **shared → parent** | list[Warning] | `operator.add` |
| progress | **shared → parent** | list[ProgressEvent] | `operator.add` |

Private keys never reach the parent (subgraph `output` schema = `{scorecards, warnings, progress}`),
so document text and PDF bytes are discarded when the branch ends (FR-035).

## ProgressEvent

`{"supplier_index": int | None, "supplier_name": str | None, "stage": str}` where stage ∈
`waiting, extracting, evaluating, retrying, done, flagged, failed, scoring, benchmarking,
ranking, persisting, completed, run_failed`.

## Routing contract

- `create_run → [Send("supplier_eval", {...}) per supplier]`; exception → `mark_failed`.
- `validate → call_llm` iff `needs_retry and attempts < 2`; else `normalize`.
- after fan-in: if every scorecard has `evaluation_failed` → `mark_failed`
  (reason "no supplier received a usable AI response"); else `score`.
- `persist` exception → `mark_failed`. `mark_failed → END`, `persist → END`.
