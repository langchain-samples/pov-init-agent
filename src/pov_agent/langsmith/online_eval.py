"""Online code evaluator — runs server-side on live production traces.

Uploaded with:
    langsmith evaluator upload online_eval.py --function perform_eval \
        --name report-structure --project <project> --sampling-rate 1.0

Constraints of the online code-evaluator sandbox: the function takes exactly one
positional ``run`` argument, has NO network access, and may use only the standard
library plus numpy/pandas/scipy/scikit-learn/jsonschema. It therefore CANNOT import
this repo, so the structure logic below is duplicated from ``evaluators.py``.

# ponytail: deliberate duplication — the sandbox forbids importing repo code.
# If you change the structure rule here, change score_report_structure() too.
"""

EXPECTED_SECTIONS = [
    "executive summary",
    "background",
    "key findings",
    "recommendations",
    "conclusion",
]
MIN_WORDS = 200


def _final_report_text(run) -> str:
    """Pull the final report out of a serialized run's outputs."""
    outputs = (run or {}).get("outputs") or {}
    messages = outputs.get("messages") or []
    # Walk messages from the end; return the last substantial text content.
    for message in reversed(messages):
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):  # content blocks
            content = " ".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        if isinstance(content, str) and content.strip():
            return content
    # Fallback: a flat string output.
    if isinstance(outputs.get("report"), str):
        return outputs["report"]
    return ""


def perform_eval(run):
    report = _final_report_text(run)
    text = report.lower()
    present = sum(1 for s in EXPECTED_SECTIONS if s in text)
    score = present / len(EXPECTED_SECTIONS)
    if len(report.split()) < MIN_WORDS:
        score *= 0.5
    return {"report_structure": round(score, 3)}
