"""
Alpha Formatter Tool — Tool 3 for the ReAct Agent.
An LLM-based tool that takes raw paper text (title, authors, abstract, etc.)
and extracts it into a structured Alpha JSON with exactly 6 top-level fields
and 5 nested logic fields.
Self-correction: if any required field is missing, returns a validation error
string so the Agent can retry with better input.
"""
import json
import os
import re
from typing import Any, Dict
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()
# ── Required schema ───────────────────────────────────────────────────────────
TOP_LEVEL_FIELDS = ["title", "author", "abstract", "url", "published_date", "logic"]
LOGIC_FIELDS = ["category", "input_variable", "economic_rationale", "trading_logic", "direction"]
SYSTEM_PROMPT = """You are a quantitative finance extraction engine.
Given raw text about an academic paper, extract and return ONLY a valid JSON object with this exact schema:
{
  "title": "full paper title",
  "author": "author name(s)",
  "abstract": "brief abstract summary (2-3 sentences)",
  "url": "arxiv paper URL",
  "published_date": "YYYY-MM-DD",
  "logic": {
    "category": "momentum / mean-reversion / value / quality / volatility / other",
    "input_variable": "variables used (e.g. past 12-month returns, volume, turnover)",
    "economic_rationale": "concise explanation of why this strategy should generate alpha",
    "trading_logic": "step-by-step description of the trading strategy",
    "direction": "long / short / long-short / market-neutral"
  }
}
Rules:
- Return ONLY raw JSON — no markdown, no explanation, no code fences.
- Every field is required. Use "N/A" if information is not available in the input.
- published_date must follow YYYY-MM-DD format strictly.
- direction must be one of: long, short, long-short, market-neutral.
"""
# ── Core formatter function ───────────────────────────────────────────────────
def alpha_formatter(text: str) -> str:
    """Extract structured Alpha JSON from raw paper text using an LLM call.
    Args:
        text: Raw paper content — title, authors, abstract, URL, date combined.
    Returns:
        A JSON string of the structured Alpha object on success.
        A validation error string (prefixed with [VALIDATION ERROR]) if fields
        are missing, so the ReAct Agent knows to retry.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("DEFAULT_MODEL", "gpt-4o")
    if not api_key:
        return "[ERROR] OPENAI_API_KEY not set in environment."
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract Alpha from this paper:\n\n{text}"},
            ],
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if model added them despite instructions
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return f"[VALIDATION ERROR] LLM returned invalid JSON: {exc}. Raw output: {raw[:300]}"
    except Exception as exc:
        return f"[ERROR] alpha_formatter failed: {exc}"
    # ── Field validation ──────────────────────────────────────────────────────
    validation_errors = _validate(parsed)
    if validation_errors:
        missing = ", ".join(validation_errors)
        return (
            f"[VALIDATION ERROR] Missing or empty required fields: {missing}. "
            f"Please provide more complete paper information and retry."
        )
    return json.dumps(parsed, ensure_ascii=False, indent=2)
def _validate(data: Dict[str, Any]) -> list[str]:
    """Return a list of missing/empty field paths. Empty list means valid.

    "N/A" is accepted (model is instructed to use it when information is
    genuinely unavailable), so only None and "" are treated as missing.
    """
    errors = []
    for field in TOP_LEVEL_FIELDS:
        if field == "logic":
            continue
        if field not in data or data[field] in (None, ""):
            errors.append(field)
    logic = data.get("logic")
    if not isinstance(logic, dict):
        errors.append("logic (must be an object)")
    else:
        for sub in LOGIC_FIELDS:
            if sub not in logic or logic[sub] in (None, ""):
                errors.append(f"logic.{sub}")
    return errors
# ── Tool Registry Entry ───────────────────────────────────────────────────────
ALPHA_FORMATTER_TOOL = {
    "name": "alpha_formatter",
    "description": (
        "LLM-based tool that extracts structured Alpha trading logic from raw paper text. "
        "Input: a string containing the paper's title, authors, abstract, URL, and published date. "
        "Returns a JSON object with fields: title, author, abstract, url, published_date, "
        "and a nested logic object (category, input_variable, economic_rationale, "
        "trading_logic, direction). "
        "Returns a [VALIDATION ERROR] string if required fields are missing — retry with more complete input."
    ),
    "function": alpha_formatter,
}