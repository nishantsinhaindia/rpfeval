import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rfp_eval import db, scoring  # noqa: E402
from rfp_eval.validation import normalize, parse_json  # noqa: E402

CRIT = [
    {"criterion_id": 1, "name": "Tech", "description": "", "weight": 60, "max_score": 10},
    {"criterion_id": 2, "name": "Price", "description": "", "weight": 40, "max_score": 10},
]


def card(name, s1, s2):
    return {"supplier_name": name, "criteria": [{"criterion_id": 1, "score": s1}, {"criterion_id": 2, "score": s2}]}


def test_absolute_score():
    assert scoring.absolute_score(card("A", 8, 5), CRIT) == 0.8 * 60 + 0.5 * 40


def test_benchmark_gap_relative_ppi():
    cards = [card("A", 8, 5), card("B", 4, 10)]
    b = scoring.benchmarks(cards, CRIT)
    assert b == {1: 8, 2: 10}
    rows, ppi, _ = scoring.peer_metrics(cards[1], CRIT, b)
    assert rows[0]["gap"] == -4 and rows[0]["relative_pct"] == 50
    assert rows[1]["gap"] == 0 and rows[1]["relative_pct"] == 100
    assert ppi == (60 * 50 + 40 * 100) / 100


def test_zero_benchmark_safe():
    cards = [card("A", 0, 5), card("B", 0, 5)]
    rows, ppi, warns = scoring.peer_metrics(cards[0], CRIT, scoring.benchmarks(cards, CRIT))
    assert rows[0]["relative_pct"] == 0 and warns


def s(name, ppi, d, exp):
    return {"supplier_name": name, "ppi": ppi, "submission_date": d, "experience_rating": exp}


def test_tie_breaks_full_order():
    out = scoring.rank_suppliers([
        s("Zeta", 90, "2026-01-02", 3),
        s("Beta", 90, "2026-01-01", 3),  # earlier date wins
        s("Alpha", 90, "2026-01-02", 5),  # higher experience wins
        s("Gamma", 95, "2026-01-05", 1),  # highest PPI
        s("Delta", 90, "2026-01-02", 3),  # name A-Z vs Zeta
    ])
    assert [x["supplier_name"] for x in out] == ["Gamma", "Beta", "Alpha", "Delta", "Zeta"]
    assert [x["final_rank"] for x in out] == [1, 2, 3, 4, 5]


def test_ranking_deterministic():
    data = [s("A", 80, "2026-01-01", 3), s("B", 80, "2026-01-01", 3), s("C", 70, "2026-01-01", 3)]
    assert scoring.rank_suppliers(data) == scoring.rank_suppliers(list(reversed(data)))


def test_validation_fills_clips_and_warns():
    raw = json.dumps({"criteria": [{"criterion_id": 1, "score": 14, "evidence": "x"},
                                   {"criterion_id": 9, "score": 3}]})
    sc, warns = normalize(parse_json(raw), "A", CRIT)
    assert [r.score for r in sc.criteria] == [10, 0]
    assert any("clipped" in w for w in warns) and any("missing" in w for w in warns)
    assert any("inactive/unknown" in w for w in warns)


def test_validation_non_numeric_and_fenced_json():
    sc, warns = normalize(parse_json('```json\n{"criteria":[{"criterion_id":1,"score":"high"},'
                                     '{"criterion_id":2,"score":7}]}\n```'), "A", CRIT)
    assert sc.criteria[0].score == 0 and sc.criteria[1].score == 7 and warns


def test_graph_end_to_end_with_fake_llm(tmp_path):
    from rfp_eval.graph import run_evaluation
    import scripts.make_synthetic_pdfs as gen
    gen.OUT = str(tmp_path)  # don't overwrite the committed sample PDFs
    SUPPLIERS, build = gen.SUPPLIERS, gen.build
    p = str(tmp_path / "t.db")
    db.init_db(p)
    pdf = open(build("Apex_Systems", SUPPLIERS["Apex_Systems"]), "rb").read()
    calls = {"n": 0}

    def fake_llm(messages):
        calls["n"] += 1
        if calls["n"] == 1:
            return "not json"  # forces one retry
        return json.dumps({"criteria": [{"criterion_id": i, "score": 7, "evidence": "e", "justification": "j"}
                                        for i in range(1, 6)], "risks": [], "overall_summary": "ok"})

    sups = [{"supplier_name": n, "submission_date": "2026-01-01", "experience_rating": 3, "pdf_bytes": pdf}
            for n in ("A", "B")]
    out = run_evaluation(sups, llm=fake_llm, db_path=p)
    assert out["status"] == "COMPLETED"
    assert [x["final_rank"] for x in out["result"]["leaderboard"]] == [1, 2]
    assert db.get_run_result(out["rfp_run_id"], p)["leaderboard"]
