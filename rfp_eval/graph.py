"""LangGraph orchestration: parent graph (Orchestrator) + supplier_eval subgraph.

Parent:   load_criteria -> create_run -> [Send x N] supplier_eval -> score -> benchmark -> rank -> persist
Subgraph: extract_pdf -> call_llm -> validate -(retry once on bad JSON)-> normalize
Shared keys between parent and subgraph: `scorecards`, `warnings` (merged with operator.add reducers).
"""
import operator
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from rfp_eval import db, scoring
from rfp_eval.evaluator import build_messages, call_llm
from rfp_eval.pdf_tool import extract_text
from rfp_eval.validation import normalize, parse_json

MAX_LLM_ATTEMPTS = 2  # first try + one retry


class RFPRunState(TypedDict, total=False):
    rfp_run_id: str
    criteria: list[dict]
    suppliers: list[dict]  # {supplier_name, submission_date, experience_rating, pdf_bytes}
    scorecards: Annotated[list[dict], operator.add]
    warnings: Annotated[list[str], operator.add]
    scored: list[dict]
    benchmarks: dict
    leaderboard: list[dict]
    status: str
    error: str
    result: dict


class SupplierEvalState(TypedDict, total=False):
    supplier: dict
    eval_criteria: list[dict]  # private copy (parent key `criteria` must not be written concurrently)
    text: str          # private
    raw_llm: str       # private
    parsed: Any        # private
    attempts: int      # private
    scorecards: Annotated[list[dict], operator.add]  # shared with parent
    warnings: Annotated[list[str], operator.add]     # shared with parent


# ---------------- supplier_eval subgraph ----------------

def build_supplier_subgraph(llm: Callable[[list[dict]], str] = call_llm):
    def extract_pdf(s: SupplierEvalState):
        name = s["supplier"]["supplier_name"]
        try:
            text = extract_text(s["supplier"]["pdf_bytes"])
        except Exception as e:
            return {"text": "", "warnings": [f"{name}: PDF could not be read ({e})"]}
        if not text.strip():
            return {"text": "", "warnings": [f"{name}: PDF has no extractable text"]}
        return {"text": text}

    def evaluate(s: SupplierEvalState):
        name = s["supplier"]["supplier_name"]
        attempts = s.get("attempts", 0) + 1
        if not s.get("text"):
            return {"raw_llm": "", "parsed": None, "attempts": MAX_LLM_ATTEMPTS}
        try:
            raw = llm(build_messages(s["eval_criteria"], name, s["text"]))
        except Exception as e:
            return {"raw_llm": "", "parsed": None, "attempts": attempts,
                    "warnings": [f"{name}: LLM call failed on attempt {attempts} ({type(e).__name__}: {e})"]}
        try:
            return {"raw_llm": raw, "parsed": parse_json(raw), "attempts": attempts}
        except ValueError as e:
            return {"raw_llm": raw, "parsed": None, "attempts": attempts,
                    "warnings": [f"{name}: invalid JSON on attempt {attempts} ({e})"]}

    def route_after_eval(s: SupplierEvalState):
        if s.get("parsed") is None and s.get("attempts", 0) < MAX_LLM_ATTEMPTS:
            return "evaluate"
        return "normalize"

    def normalize_node(s: SupplierEvalState):
        name = s["supplier"]["supplier_name"]
        card, warns = normalize(s.get("parsed") or {}, name, s["eval_criteria"])
        if s.get("parsed") is None:
            warns = [f"{name}: evaluation failed; all criteria scored 0"] + [
                w for w in warns if "missing result" not in w]
        data = card.model_dump()
        data["supplier_name"] = name  # never trust the LLM's name
        return {"scorecards": [data], "warnings": warns}

    g = StateGraph(SupplierEvalState)
    g.add_node("extract_pdf", extract_pdf)
    g.add_node("evaluate", evaluate)
    g.add_node("normalize", normalize_node)
    g.add_edge(START, "extract_pdf")
    g.add_edge("extract_pdf", "evaluate")
    g.add_conditional_edges("evaluate", route_after_eval, ["evaluate", "normalize"])
    g.add_edge("normalize", END)
    return g.compile()


# ---------------- parent graph ----------------

def build_graph(llm: Callable[[list[dict]], str] = call_llm, db_path: str | None = None):
    def load_criteria(s: RFPRunState):
        criteria = db.load_criteria(active_only=True, path=db_path)
        if not criteria:
            return {"status": "FAILED", "error": "No active criteria."}
        total = sum(c["weight"] for c in criteria)
        if abs(total - 100) > 1e-6:
            return {"status": "FAILED", "error": f"Active criteria weights total {total}, must be 100."}
        return {"criteria": criteria, "status": "RUNNING"}

    def create_run(s: RFPRunState):
        run_id = "RFP-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        db.create_run(run_id, path=db_path)
        return {"rfp_run_id": run_id}

    def fan_out(s: RFPRunState):
        return [Send("supplier_eval", {"supplier": sup, "eval_criteria": s["criteria"], "attempts": 0})
                for sup in s["suppliers"]]

    def score(s: RFPRunState):
        order = {sup["supplier_name"]: i for i, sup in enumerate(s["suppliers"])}
        cards = sorted(s["scorecards"], key=lambda c: order[c["supplier_name"]])
        scored = [dict(card, absolute_score=scoring.absolute_score(card, s["criteria"])) for card in cards]
        return {"scored": scored}

    def benchmark(s: RFPRunState):
        bench = scoring.benchmarks(s["scored"], s["criteria"])
        meta = {sup["supplier_name"]: sup for sup in s["suppliers"]}
        out, warns = [], []
        for card in s["scored"]:
            rows, ppi, w = scoring.peer_metrics(card, s["criteria"], bench)
            warns.extend(w)
            m = meta[card["supplier_name"]]
            out.append({
                "supplier_name": card["supplier_name"],
                "submission_date": m["submission_date"],
                "experience_rating": m["experience_rating"],
                "absolute_score": card["absolute_score"],
                "ppi": ppi,
                "criteria": rows,
                "risks": card.get("risks", []),
                "overall_summary": card.get("overall_summary", ""),
            })
        return {"scored": out, "benchmarks": {str(k): v for k, v in bench.items()},
                "warnings": sorted(set(warns))}

    def rank(s: RFPRunState):
        return {"leaderboard": scoring.rank_suppliers(s["scored"])}

    def persist(s: RFPRunState):
        result = {
            "rfp_run_id": s["rfp_run_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "criteria_snapshot": s["criteria"],
            "benchmarks": s["benchmarks"],
            "tie_break_order": ["PPI desc", "submission_date asc", "experience_rating desc", "supplier_name asc"],
            "leaderboard": s["leaderboard"],
            "warnings": s.get("warnings", []),
        }
        db.save_supplier_results(s["rfp_run_id"], s["leaderboard"], path=db_path)
        db.set_run_status(s["rfp_run_id"], "COMPLETED", result, path=db_path)
        return {"status": "COMPLETED", "result": result}

    def after_criteria(s: RFPRunState):
        return END if s.get("status") == "FAILED" else "create_run"

    g = StateGraph(RFPRunState)
    g.add_node("load_criteria", load_criteria)
    g.add_node("create_run", create_run)
    g.add_node("supplier_eval", build_supplier_subgraph(llm))
    g.add_node("score", score)
    g.add_node("benchmark", benchmark)
    g.add_node("rank", rank)
    g.add_node("persist", persist)
    g.add_edge(START, "load_criteria")
    g.add_conditional_edges("load_criteria", after_criteria, ["create_run", END])
    g.add_conditional_edges("create_run", fan_out, ["supplier_eval"])
    g.add_edge("supplier_eval", "score")
    g.add_edge("score", "benchmark")
    g.add_edge("benchmark", "rank")
    g.add_edge("rank", "persist")
    g.add_edge("persist", END)
    return g.compile()


def run_evaluation(suppliers: list[dict], llm=call_llm, db_path: str | None = None, on_event=None) -> dict:
    graph = build_graph(llm, db_path)
    state: dict = {"suppliers": suppliers, "scorecards": [], "warnings": []}
    final = None
    try:
        for chunk in graph.stream(state, stream_mode="values"):
            final = chunk
            if on_event:
                on_event(chunk)
    except Exception as e:
        run_id = (final or {}).get("rfp_run_id")
        if run_id:
            db.set_run_status(run_id, "FAILED", {"error": str(e)}, path=db_path)
        return {"status": "FAILED", "error": f"{type(e).__name__}: {e}", "rfp_run_id": run_id}
    return final
