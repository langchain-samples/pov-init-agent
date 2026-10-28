"""Online code evaluator — runs server-side on live production traces.

Uploaded with:
    langsmith evaluator upload online_eval.py --function perform_eval \
        --name cites-sources --project <project> --sampling-rate 1.0

Constraints of the online code-evaluator sandbox: the function takes exactly one
positional ``run`` argument, has NO network access, and may use only the standard
library plus numpy/pandas/scipy/scikit-learn/jsonschema. It therefore CANNOT import
this repo, so the citation rule below is duplicated from ``evaluators.py``, and every
helper lives inside ``perform_eval`` (the sandbox doesn't keep module-level names).

# ponytail: deliberate duplication — the sandbox forbids importing repo code.
# If you change the citation rule here, change cites_sources_evaluator() too.
"""


def perform_eval(run):
    import re

    outputs = (run or {}).get("outputs") or {}
    answer = ""
    for message in reversed(outputs.get("messages") or []):
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            content = " ".join(
                b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
            )
        if isinstance(content, str) and content.strip():
            answer = content
            break
    if not answer and isinstance(outputs.get("answer"), str):
        answer = outputs["answer"]

    lines = re.findall(r"^\s*\**sources?\**\s*:\s*(.+)$", answer, re.IGNORECASE | re.MULTILINE)
    cited = [t.strip(" `*[]().") for line in lines for t in re.split(r"[,;]", line) if t.strip(" `*[]().")]
    return {"cites_sources": 1.0 if cited else 0.0}
