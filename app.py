"""Streamlit UI for Agentic RFP Evaluation and Supplier Ranking."""
import json
from datetime import date

import pandas as pd
import streamlit as st

from rfp_eval import db
from rfp_eval.evaluator import get_api_key
from rfp_eval.graph import run_evaluation

st.set_page_config(page_title="Agentic RFP Evaluation", page_icon="📑", layout="wide")
db.init_db()

st.title("📑 Agentic RFP Evaluation & Supplier Ranking")
st.caption("LLM judges proposal content · LangGraph orchestrates · deterministic Python scores, benchmarks and ranks.")

tab_eval, tab_criteria, tab_history = st.tabs(["Evaluate", "Criteria", "Run history"])

# ---------------- Criteria ----------------
with tab_criteria:
    st.subheader("Evaluation criteria")
    all_crit = pd.DataFrame(db.load_criteria(active_only=False))
    all_crit["is_active"] = all_crit["is_active"].astype(bool)
    edited = st.data_editor(
        all_crit, hide_index=True, use_container_width=True,
        disabled=["criterion_id", "name", "description"],
        column_config={"weight": st.column_config.NumberColumn("weight (%)", min_value=0, max_value=100),
                       "max_score": st.column_config.NumberColumn(min_value=1)},
        key="crit_editor",
    )
    active_total = edited.loc[edited["is_active"], "weight"].sum()
    st.write(f"Active weight total: **{active_total:g}%**")
    if st.button("Save criteria"):
        if abs(active_total - 100) > 1e-6:
            st.error("Active weights must total 100% before saving.")
        else:
            db.save_criteria(edited.to_dict("records"))
            st.success("Criteria saved.")
            st.rerun()


def render_result(result: dict):
    lb = result["leaderboard"]
    st.subheader("🏆 Leaderboard")
    st.dataframe(pd.DataFrame([{
        "Rank": s["final_rank"], "Supplier": s["supplier_name"],
        "Absolute score": round(s["absolute_score"], 2), "PPI": round(s["ppi"], 2),
        "Submission date": s["submission_date"], "Experience rating": s["experience_rating"],
        "Why this position": s["tie_break_explanation"],
    } for s in lb]), hide_index=True, use_container_width=True)

    st.subheader("Detailed scorecards")
    for s in lb:
        with st.expander(f"#{s['final_rank']} {s['supplier_name']} — PPI {s['ppi']:.2f}, absolute {s['absolute_score']:.2f}"):
            st.dataframe(pd.DataFrame([{
                "Criterion": r["criterion_name"], "Weight": r["weight"], "Score": r["score"],
                "Max": r["max_score"], "Benchmark": r["benchmark"], "Gap": r["gap"],
                "Relative %": round(r["relative_pct"], 1), "Evidence": r["evidence"],
                "Justification": r["justification"],
            } for r in s["criteria"]]), hide_index=True, use_container_width=True)
            if s.get("overall_summary"):
                st.markdown(f"**Summary:** {s['overall_summary']}")
            if s.get("risks"):
                st.markdown("**Risks:** " + "; ".join(s["risks"]))

    st.subheader("Run details")
    st.write(f"**RFP_RUN_ID:** `{result['rfp_run_id']}`")
    st.write("**Tie-break order:** Higher PPI → earlier submission date → higher experience rating → supplier name A–Z")
    if result.get("warnings"):
        st.warning("Validation warnings:\n\n" + "\n".join(f"- {w}" for w in result["warnings"]))
    else:
        st.info("No validation warnings.")
    st.download_button("⬇️ Download complete result (JSON)", json.dumps(result, indent=2),
                       file_name=f"{result['rfp_run_id']}.json", mime="application/json")


# ---------------- Evaluate ----------------
with tab_eval:
    active = db.load_criteria()
    st.subheader("Active criteria")
    st.dataframe(pd.DataFrame(active)[["criterion_id", "name", "description", "weight", "max_score"]],
                 hide_index=True, use_container_width=True)
    total = sum(c["weight"] for c in active)
    if abs(total - 100) > 1e-6:
        st.error(f"Active weights total {total:g}%, must be 100%. Fix them in the Criteria tab.")

    st.subheader("Supplier proposals")
    files = st.file_uploader("Upload supplier RFP PDFs", type=["pdf"], accept_multiple_files=True)
    suppliers, errors = [], []
    for i, f in enumerate(files or []):
        default_name = f.name.rsplit(".", 1)[0].replace("_", " ")
        c1, c2, c3 = st.columns([3, 2, 2])
        name = c1.text_input("Supplier name", default_name, key=f"n{i}")
        sub = c2.date_input("Submission date", date.today(), key=f"d{i}")
        exp = c3.number_input("Experience rating (1–5)", 1.0, 5.0, 3.0, 0.5, key=f"e{i}")
        data = f.getvalue()
        if not name.strip():
            errors.append(f"File {f.name}: supplier name is required.")
        if sub > date.today():
            errors.append(f"{name}: submission date cannot be in the future.")
        if len(data) > 10 * 1024 * 1024:
            errors.append(f"{name}: file is larger than 10 MB.")
        if not data.startswith(b"%PDF"):
            errors.append(f"{name}: file is not a valid PDF.")
        suppliers.append({"supplier_name": name.strip(), "submission_date": sub.isoformat(),
                          "experience_rating": float(exp), "pdf_bytes": data})
    names = [s["supplier_name"].lower() for s in suppliers]
    if len(names) != len(set(names)):
        errors.append("Supplier names must be unique within a run.")
    if files and len(files) < 2:
        st.info("Tip: upload at least 2 suppliers for a meaningful peer comparison.")
    for e in errors:
        st.error(e)
    if not get_api_key():
        st.error("OPENAI_API_KEY is not configured (set it in Streamlit secrets or the environment).")

    if st.button("🚀 Evaluate", type="primary",
                 disabled=not suppliers or bool(errors) or abs(total - 100) > 1e-6 or not get_api_key()):
        with st.status("Running LangGraph workflow…", expanded=True) as status:
            seen = set()

            def on_event(state):
                for card in state.get("scorecards", []):
                    if card["supplier_name"] not in seen:
                        seen.add(card["supplier_name"])
                        st.write(f"✅ Evaluated {card['supplier_name']}")

            out = run_evaluation(suppliers, on_event=on_event)
            if out.get("status") == "COMPLETED":
                status.update(label="Evaluation complete", state="complete")
                st.session_state["last_result"] = out["result"]
            else:
                status.update(label="Evaluation failed", state="error")
                st.error(out.get("error", "Unknown error"))
    if st.session_state.get("last_result"):
        render_result(st.session_state["last_result"])

# ---------------- History ----------------
with tab_history:
    runs = db.list_runs()
    if not runs:
        st.info("No runs yet.")
    else:
        st.dataframe(pd.DataFrame(runs), hide_index=True, use_container_width=True)
        pick = st.selectbox("Open run", [r["rfp_run_id"] for r in runs if r["status"] == "COMPLETED"])
        if pick:
            res = db.get_run_result(pick)
            if res:
                render_result(res)
