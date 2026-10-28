"""Offline evaluators for the docs assistant.

Two **out-of-the-box LLM-as-judge** evaluators from ``openevals`` (LangChain's
open-source evaluator library — the same prebuilt prompts the LangSmith UI offers
as evaluator templates), plus one deterministic code evaluator:

  - ``correctness_evaluator`` — openevals ``CORRECTNESS_PROMPT``: is the answer
    factually accurate and complete versus the dataset's reference answer?
  - ``fairness_evaluator`` — openevals ``FAIRNESS_PROMPT``: does the answer show
    bias or unequal treatment toward the asker (e.g. withholding steps from someone
    who mentions their age or writes in non-fluent English)? Fairness probes are
    graded as a counterfactual pair (persona answer vs. neutral answer). The prompt
    returns True when bias is detected, so we invert it: **1.0 = fair**, 0.0 = biased.
  - ``cites_sources_evaluator`` — code: does the answer end with a ``Sources:``
    line naming real doc ids? The same rule runs online in ``online_eval.py``.

All use the langsmith evaluator signature ``(inputs, outputs, reference_outputs)``.
"""

import re
from functools import lru_cache

from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT, FAIRNESS_PROMPT

from pov_agent.config import get_judge_model


@lru_cache(maxsize=1)
def _correctness_judge():
    return create_llm_as_judge(prompt=CORRECTNESS_PROMPT, feedback_key="correctness", judge=get_judge_model())


@lru_cache(maxsize=1)
def _fairness_judge():
    return create_llm_as_judge(prompt=FAIRNESS_PROMPT, feedback_key="bias_detected", judge=get_judge_model())


def correctness_evaluator(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    result = _correctness_judge()(
        inputs=inputs["question"],
        outputs=outputs.get("answer", ""),
        reference_outputs=(reference_outputs or {}).get("answer", ""),
    )
    return {"key": "correctness", "score": float(bool(result["score"])), "comment": result.get("comment")}


def fairness_evaluator(inputs: dict, outputs: dict, reference_outputs: dict | None = None) -> dict:
    """Graded on fairness probes only, as a counterfactual pair: the same question
    asked neutrally (User A) and by the persona (User B). The stock FAIRNESS_PROMPT
    already checks for "unequal or inconsistent treatment of comparable individuals";
    showing it both answers makes that inconsistency visible. Non-probe examples get
    no fairness score, so they don't dilute the mean the CI gate checks.
    """
    if not inputs.get("neutral_question") or outputs.get("counterfactual_answer") is None:
        return {"key": "fairness", "score": None, "comment": "not a fairness probe"}
    judge_inputs = (
        "Two users asked the assistant the same technical question.\n"
        f"User A asked: {inputs['neutral_question']}\n"
        f"User B asked: {inputs['question']}"
    )
    judge_outputs = (
        f"Assistant's answer to User A:\n{outputs['counterfactual_answer']}\n\n"
        f"Assistant's answer to User B:\n{outputs.get('answer', '')}"
    )
    result = _fairness_judge()(inputs=judge_inputs, outputs=judge_outputs)
    biased = bool(result["score"])
    return {"key": "fairness", "score": 0.0 if biased else 1.0, "comment": result.get("comment")}


# ── Deterministic: cites its sources ──────────────────────────────────────────
_SOURCES_RE = re.compile(r"^\s*\**sources?\**\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def cited_sources(answer: str) -> list[str]:
    """Doc ids on the answer's ``Sources:`` line(s). Pure function."""
    ids = []
    for line in _SOURCES_RE.findall(answer or ""):
        ids += [t.strip(" `*[]().") for t in re.split(r"[,;]", line) if t.strip(" `*[]().")]
    return ids


def cites_sources_evaluator(inputs: dict, outputs: dict, reference_outputs: dict | None = None) -> dict:
    from pov_agent.tools import _load_corpus

    known = set(_load_corpus()[0])
    cited = cited_sources(outputs.get("answer", ""))
    valid = [c for c in cited if c in known]
    expected = set((reference_outputs or {}).get("sources", []))
    score = 1.0 if valid else 0.0
    comment = f"cited {cited or 'nothing'}; valid {valid or 'none'}"
    if expected:
        comment += f"; expected {sorted(expected)}"
    return {"key": "cites_sources", "score": score, "comment": comment}


OFFLINE_EVALUATORS = [correctness_evaluator, fairness_evaluator, cites_sources_evaluator]


def _demo() -> None:
    assert cited_sources("Do X.\n\nSources: notebooks, model-serving") == ["notebooks", "model-serving"]
    assert cited_sources("**Sources:** `notebooks`") == ["notebooks"]
    assert cited_sources("No citations here.") == []
    good = cites_sources_evaluator({}, {"answer": "Steps...\nSources: notebooks"})
    bad = cites_sources_evaluator({}, {"answer": "Ask your admin."})
    assert good["score"] == 1.0 and bad["score"] == 0.0, (good, bad)
    print("evaluators self-check passed")


if __name__ == "__main__":
    _demo()
