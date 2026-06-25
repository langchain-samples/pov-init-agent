"""Create the human-review annotation queue and seed it with runs. Idempotent.

Feedback configs are org-wide reusable schemas; the queue's rubric assigns which
ones reviewers must fill out.
"""

from pov_agent.config import QUEUE_NAME

_FEEDBACK_CONFIGS = [
    ("report_quality", {"type": "continuous", "min": 0, "max": 1}, False),
    (
        "factually_grounded",
        {"type": "categorical", "categories": [{"value": 1, "label": "Pass"}, {"value": 0, "label": "Fail"}]},
        None,
    ),
    ("reviewer_notes", {"type": "freeform"}, None),
]

_RUBRIC_ITEMS = [
    {
        "feedback_key": "report_quality",
        "description": "Overall usefulness and clarity of the report.",
        "score_descriptions": {"0": "Unusable", "1": "Excellent — ship it"},
        "is_required": True,
    },
    {
        "feedback_key": "factually_grounded",
        "description": "Are the claims sound, with no fabricated facts or citations?",
        "value_descriptions": {"Pass": "Claims are sound", "Fail": "Contains fabrication or errors"},
        "is_required": True,
    },
    {
        "feedback_key": "reviewer_notes",
        "description": "Anything notable for the team.",
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
        description="Human review of generated reports for quality and factual grounding.",
        rubric_instructions="Read the report and score it. Flag anything fabricated. Notes welcome.",
        rubric_items=_RUBRIC_ITEMS,
    )

    if run_ids:
        client.add_runs_to_annotation_queue(queue.id, run_ids=run_ids[:5])
    return queue
