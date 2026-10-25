"""Evaluation Agent: build evidence-grounded prompt and call the LLM (JSON only)."""
import json
import os

SYSTEM = """You are a procurement evaluator. Score ONE supplier proposal against the given criteria.
Rules:
- Use ONLY evidence present in the supplier document. Never invent facts. If there is no evidence, give a low score and set evidence to "no evidence found".
- Return exactly one result for EVERY criterion listed, using its criterion_id.
- Each score must be a number between 0 and that criterion's max_score.
- "evidence" must be a short verbatim quote from the document.
- Do not compute totals, weights, or rankings.
- Output JSON only, no markdown, matching:
{"supplier_name": str, "criteria": [{"criterion_id": int, "score": number, "max_score": number, "justification": str, "evidence": str}], "risks": [str], "overall_summary": str}"""


def build_messages(criteria: list[dict], supplier_name: str, text: str) -> list[dict]:
    crit = [{"criterion_id": c["criterion_id"], "name": c["name"], "what_to_inspect": c["description"],
             "max_score": c["max_score"]} for c in criteria]
    user = (f"Supplier name: {supplier_name}\n\nCriteria:\n{json.dumps(crit, indent=2)}\n\n"
            f"Supplier document:\n<<<\n{text}\n>>>")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def get_api_key() -> str | None:
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get("OPENAI_API_KEY")
    except Exception:
        return None


def get_model() -> str:
    try:
        import streamlit as st
        return os.environ.get("OPENAI_MODEL") or st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")
    except Exception:
        return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def call_llm(messages: list[dict]) -> str:
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model=get_model(), temperature=0, api_key=get_api_key(), timeout=90, max_retries=2,
                     model_kwargs={"response_format": {"type": "json_object"}})
    return llm.invoke([(m["role"], m["content"]) for m in messages]).content
