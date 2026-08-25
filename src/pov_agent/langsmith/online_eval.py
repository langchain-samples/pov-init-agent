"""Online code evaluator — runs server-side on live production traces.

Uploaded with:
    langsmith evaluator upload online_eval.py --function perform_eval \
        --name match-structure --project <project> --sampling-rate 1.0

Constraints of the online code-evaluator sandbox: the function takes exactly one
positional ``run`` argument, has NO network access, and may use only the standard
library plus numpy/pandas/scipy/scikit-learn/jsonschema. It therefore CANNOT import
this repo, so the structure + score-parsing logic below is duplicated from
``evaluators.py``.

# ponytail: deliberate duplication — the sandbox forbids importing repo code.
# If you change the structure rule here, change score_review_structure() too.
"""

import re

EXPECTED_SECTIONS = [
    "match summary",
    "strengths",
    "gaps",
    "recommendation",
]
MIN_WORDS = 120
_SCORE_RE = re.compile(r"match\s*score\s*[:=]\s*([01](?:\.\d+)?)", re.IGNORECASE)


def _parse_match_score(review):
    match = _SCORE_RE.search(review or "")
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return value if 0.0 <= value <= 1.0 else None


def _final_review_text(run) -> str:
    """Pull the final review out of a serialized run's outputs."""
    outputs = (run or {}).get("outputs") or {}
    messages = outputs.get("messages") or []
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
    if isinstance(outputs.get("review"), str):
        return outputs["review"]
    return ""


def perform_eval(run):
    review = _final_review_text(run)
    text = review.lower()
    present = sum(1 for s in EXPECTED_SECTIONS if s in text)
    score = present / len(EXPECTED_SECTIONS)
    if _parse_match_score(review) is None:
        score *= 0.5
    if len(review.split()) < MIN_WORDS:
        score *= 0.5
    return {"match_structure": round(score, 3)}
