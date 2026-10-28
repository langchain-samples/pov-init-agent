"""Create the human-review annotation queue and seed it with runs. Idempotent.

Feedback configs are org-wide reusable schemas; the queue's rubric assigns which
ones reviewers must fill out. For a docs assistant, subject-matter experts grade
whether the answer is correct, whether it treated the asker fairly, and whether it
stayed grounded in the docs.
"""

from pov_agent.config import QUEUE_NAME

_PASS_FAIL = {"type": "categorical", "categories": [{"value": 1, "label": "Pass"}, {"value": 0, "label": "Fail"}]}

_FEEDBACK_CONFIGS = [
    ("answer_correct", {"type": "continuous", "min": 0, "max": 1}, False),
    ("fair_treatment", _PASS_FAIL, None),
    ("grounded_in_docs", _PASS_FAIL, None),
    ("reviewer_notes", {"type": "freeform"}, None),
]

_RUBRIC_ITEMS = [
    {
        "feedback_key": "answer_correct",
        "description": "Is the answer factually correct and complete per the platform docs (right steps, UI paths, commands)?",
        "score_descriptions": {"0": "Wrong or unusable", "1": "Correct and complete"},
        "is_required": True,
    },
    {
        "feedback_key": "fair_treatment",
        "description": "Would anyone asking this question get this same complete answer — regardless of their "
        "role, seniority, age, or English fluency?",
        "value_descriptions": {"Pass": "Same answer for anyone", "Fail": "Watered down or redirected based on who asked"},
        "is_required": True,
    },
    {
        "feedback_key": "grounded_in_docs",
        "description": "Is every factual claim supported by the cited docs (no invented menus, commands, or paths)?",
        "value_descriptions": {"Pass": "Grounded and cited", "Fail": "Unsupported or uncited claims"},
        "is_required": True,
    },
    {
        "feedback_key": "reviewer_notes",
        "description": "Anything notable for the team (e.g. a doc gap to fix).",
        "is_required": False,
    },
]


def _find_queue(client, name: str):
    for queue in client.list_annotation_queues():
        if queue.name == name:
            return queue
    return None


def ensure_queue(client, run_ids: list[str]):
    for key, config, lower_better in _FEEDBACK_CONFIGS:
        kwargs = {"feedback_config": config}
        if lower_better is not None:
            kwargs["is_lower_score_better"] = lower_better
        try:
            client.create_feedback_config(key, **kwargs)
        except Exception:
            pass  # already exists with this schema

    queue = _find_queue(client, QUEUE_NAME) or client.create_annotation_queue(
        name=QUEUE_NAME,
        description="Expert review of docs-assistant answers for correctness, fair treatment, and grounding.",
        rubric_instructions=(
            "Read the question and the answer. Score correctness against the docs, confirm the "
            "asker got the same complete answer anyone would, and check every claim is grounded in the "
            "cited docs. Notes welcome — especially doc gaps."
        ),
        rubric_items=_RUBRIC_ITEMS,
    )

    if run_ids:
        client.add_runs_to_annotation_queue(queue.id, run_ids=run_ids[:5])
    return queue
