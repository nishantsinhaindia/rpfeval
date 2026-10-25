"""Ranking Tool: deterministic Python only. No LLM here."""
from datetime import date


def absolute_score(scorecard: dict, criteria: list[dict]) -> float:
    """Sum of (score / max_score) x weight."""
    by_id = {r["criterion_id"]: r for r in scorecard["criteria"]}
    total = 0.0
    for c in criteria:
        r = by_id[c["criterion_id"]]
        total += (r["score"] / c["max_score"]) * c["weight"] if c["max_score"] else 0.0
    return total


def benchmarks(scorecards: list[dict], criteria: list[dict]) -> dict[int, float]:
    """Highest valid score per criterion across all suppliers."""
    out = {}
    for c in criteria:
        cid = c["criterion_id"]
        out[cid] = max((r["score"] for s in scorecards for r in s["criteria"] if r["criterion_id"] == cid),
                       default=0.0)
    return out


def peer_metrics(scorecard: dict, criteria: list[dict], bench: dict[int, float]) -> tuple[list[dict], float, list[str]]:
    """Per-criterion gap and relative %, plus weighted PPI.
    Zero benchmark: relative % = 0 for every supplier (nobody showed capability) and a warning is recorded."""
    by_id = {r["criterion_id"]: r for r in scorecard["criteria"]}
    rows, warnings = [], []
    weighted, weight_sum = 0.0, 0.0
    for c in criteria:
        cid = c["criterion_id"]
        r = by_id[cid]
        b = bench[cid]
        if b > 0:
            rel = r["score"] / b * 100
        else:
            rel = 0.0
            warnings.append(f"Benchmark for '{c['name']}' is 0; relative % set to 0 for all suppliers")
        rows.append({
            "criterion_id": cid, "criterion_name": c["name"], "weight": c["weight"],
            "score": r["score"], "max_score": c["max_score"], "benchmark": b,
            "gap": r["score"] - b, "relative_pct": rel,
            "justification": r.get("justification", ""), "evidence": r.get("evidence", ""),
        })
        weighted += c["weight"] * rel
        weight_sum += c["weight"]
    ppi = weighted / weight_sum if weight_sum else 0.0
    return rows, ppi, warnings


def _sort_key(s: dict):
    # Round PPI to avoid float noise deciding order; then tie-breaks.
    return (-round(s["ppi"], 6), date.fromisoformat(s["submission_date"]),
            -float(s["experience_rating"]), s["supplier_name"].lower(), s["supplier_name"])


def rank_suppliers(suppliers: list[dict]) -> list[dict]:
    """PPI desc -> earlier submission date -> higher experience -> name A-Z. Sequential ranks 1..N."""
    ordered = sorted(suppliers, key=_sort_key)
    out = []
    for i, s in enumerate(ordered, start=1):
        s = dict(s, final_rank=i)
        s["tie_break_explanation"] = explain(ordered[i - 2], s) if i > 1 else "Highest PPI."
        out.append(s)
    return out


def explain(prev: dict, cur: dict) -> str:
    """Why `cur` is ranked directly below `prev`."""
    if round(prev["ppi"], 6) != round(cur["ppi"], 6):
        return f"Lower PPI than {prev['supplier_name']} ({cur['ppi']:.2f} vs {prev['ppi']:.2f})."
    if prev["submission_date"] != cur["submission_date"]:
        return f"Tied PPI with {prev['supplier_name']}; submitted later ({cur['submission_date']} vs {prev['submission_date']})."
    if float(prev["experience_rating"]) != float(cur["experience_rating"]):
        return f"Tied PPI and date with {prev['supplier_name']}; lower experience rating ({cur['experience_rating']} vs {prev['experience_rating']})."
    return f"Tied PPI, date and experience with {prev['supplier_name']}; ordered by supplier name A-Z."
