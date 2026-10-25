"""Validation Tool: parse + normalize untrusted LLM output into a complete scorecard."""
import json
import re
from typing import Any

from pydantic import BaseModel, Field


class CriterionResult(BaseModel):
    criterion_id: int
    score: float
    max_score: float
    justification: str = ""
    evidence: str = ""


class Scorecard(BaseModel):
    supplier_name: str
    criteria: list[CriterionResult]
    risks: list[str] = Field(default_factory=list)
    overall_summary: str = ""


def parse_json(raw: str) -> dict:
    """Parse JSON, tolerating markdown code fences / surrounding text. Raises ValueError."""
    if not raw or not raw.strip():
        raise ValueError("empty LLM response")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            raise ValueError("no JSON object found in LLM response")
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise ValueError(f"malformed JSON: {e}") from e


def normalize(data: Any, supplier_name: str, criteria: list[dict]) -> tuple[Scorecard, list[str]]:
    """Return a scorecard with exactly one result per active criterion, plus warnings for every fix."""
    warnings: list[str] = []
    if not isinstance(data, dict):
        warnings.append(f"{supplier_name}: LLM output was not a JSON object; all criteria scored 0")
        data = {}
    items = data.get("criteria") if isinstance(data.get("criteria"), list) else []
    if "criteria" in data and not isinstance(data.get("criteria"), list):
        warnings.append(f"{supplier_name}: 'criteria' field was not a list")
    by_id: dict[int, dict] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            cid = int(it.get("criterion_id"))
        except (TypeError, ValueError):
            warnings.append(f"{supplier_name}: dropped criterion entry with invalid id {it.get('criterion_id')!r}")
            continue
        if cid in by_id:
            warnings.append(f"{supplier_name}: duplicate result for criterion {cid}; kept the first")
            continue
        by_id[cid] = it

    active_ids = {c["criterion_id"] for c in criteria}
    for extra in sorted(set(by_id) - active_ids):
        warnings.append(f"{supplier_name}: ignored result for inactive/unknown criterion {extra}")

    results = []
    for c in criteria:
        cid, mx, name = c["criterion_id"], float(c["max_score"]), c["name"]
        it = by_id.get(cid)
        if it is None:
            warnings.append(f"{supplier_name}: missing result for '{name}'; score set to 0")
            results.append(CriterionResult(criterion_id=cid, score=0, max_score=mx,
                                           justification="Not assessed by the model.", evidence="no evidence found"))
            continue
        raw_score = it.get("score")
        try:
            score = float(raw_score)
            if score != score:  # NaN
                raise ValueError
        except (TypeError, ValueError):
            warnings.append(f"{supplier_name}: non-numeric score {raw_score!r} for '{name}'; set to 0")
            score = 0.0
        if score < 0 or score > mx:
            clipped = min(max(score, 0.0), mx)
            warnings.append(f"{supplier_name}: score {score} for '{name}' out of range 0..{mx}; clipped to {clipped}")
            score = clipped
        evidence = str(it.get("evidence") or "").strip() or "no evidence found"
        results.append(CriterionResult(criterion_id=cid, score=score, max_score=mx,
                                       justification=str(it.get("justification") or "").strip(),
                                       evidence=evidence))
    risks = data.get("risks") if isinstance(data.get("risks"), list) else []
    return Scorecard(supplier_name=supplier_name, criteria=results,
                     risks=[str(r) for r in risks], overall_summary=str(data.get("overall_summary") or "")), warnings
