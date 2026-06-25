"""Offline evaluators for the report-writer agent.

Two evaluators, deliberately different in kind:
  - ``structure_evaluator`` — a deterministic *code* eval. The same logic is
    redeployed as the online evaluator in ``online_eval.py`` (which must be
    self-contained, so the logic is duplicated there on purpose).
  - ``coverage_evaluator`` — an *LLM-as-judge* that scores how well the report
    covers the reference points for the topic.

Both use the langsmith evaluator signature ``(inputs, outputs, reference_outputs)``
and return ``{"key", "score", "comment"}``.
"""

from pydantic import BaseModel, Field

from pov_agent.config import EXPECTED_SECTIONS, get_model

MIN_WORDS = 200


def score_report_structure(report: str) -> tuple[float, str]:
    """Fraction of expected sections present, gated on a minimum length.

    Returns (score in [0,1], human-readable comment). Pure function — no I/O.
    """
    text = (report or "").lower()
    present = [s for s in EXPECTED_SECTIONS if s in text]
    missing = [s for s in EXPECTED_SECTIONS if s not in text]
    score = len(present) / len(EXPECTED_SECTIONS)

    word_count = len((report or "").split())
    if word_count < MIN_WORDS:
        score *= 0.5  # too short to be a real report, even if headings exist

    comment = f"{len(present)}/{len(EXPECTED_SECTIONS)} sections, {word_count} words"
    if missing:
        comment += f"; missing: {', '.join(missing)}"
    return round(score, 3), comment


def structure_evaluator(inputs: dict, outputs: dict, reference_outputs: dict | None = None) -> dict:
    score, comment = score_report_structure(outputs.get("report", ""))
    return {"key": "report_structure", "score": score, "comment": comment}


class _CoverageVerdict(BaseModel):
    coverage_score: float = Field(description="Fraction 0-1 of the must-cover points addressed well.")
    missing_points: list[str] = Field(default_factory=list, description="Required points not adequately covered.")
    justification: str = Field(description="One or two sentences explaining the score.")


_JUDGE_PROMPT = """You are grading a research report against a checklist of points it must cover.

TOPIC:
{topic}

POINTS THE REPORT MUST COVER:
{must_cover}

THE REPORT:
{report}

Score the fraction (0.0 to 1.0) of the required points that the report covers well.
A point counts only if it is genuinely addressed with substance, not merely mentioned.
List any points that are missing or only superficially touched, and justify your score briefly."""


def coverage_evaluator(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    must_cover = (reference_outputs or {}).get("must_cover", [])
    judge = get_model().with_structured_output(_CoverageVerdict)
    verdict: _CoverageVerdict = judge.invoke(
        _JUDGE_PROMPT.format(
            topic=inputs.get("topic", ""),
            must_cover="\n".join(f"- {p}" for p in must_cover),
            report=outputs.get("report", ""),
        )
    )
    comment = verdict.justification
    if verdict.missing_points:
        comment += f" | missing: {', '.join(verdict.missing_points)}"
    return {"key": "coverage", "score": verdict.coverage_score, "comment": comment}


def _demo() -> None:
    """Self-check for the one piece of non-trivial logic: the structure metric."""
    good = (
        "# A Specific Title\n\n## Executive Summary\n" + ("word " * 250) +
        "\n## Background\nx\n## Key Findings\nx\n## Recommendations\nx\n## Conclusion\nx"
    )
    bad = "Here are some thoughts about the topic. The end."

    good_score, _ = score_report_structure(good)
    bad_score, _ = score_report_structure(bad)
    assert good_score == 1.0, good_score
    assert bad_score == 0.0, bad_score
    # length gate halves the score even when every heading is present
    short_complete = "\n".join(f"## {s}" for s in EXPECTED_SECTIONS)
    assert score_report_structure(short_complete)[0] == 0.5
    print("evaluators self-check passed")


if __name__ == "__main__":
    _demo()
