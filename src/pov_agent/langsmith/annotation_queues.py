"""Create the human-review annotation queue and seed it with runs. Idempotent.

Feedback configs are org-wide reusable schemas; the queue's rubric assigns which
ones reviewers must fill out. For a support agent, reviewers grade whether the
issue was resolved, whether privacy policy was followed, and whether the reply
fit its channel. Reviewers see traces AFTER SDK masking, so human review never
requires exposing raw customer data.
"""

from pov_agent.config import QUEUE_NAME

_PASS_FAIL = {"type": "categorical", "categories": [{"value": 1, "label": "Pass"}, {"value": 0, "label": "Fail"}]}

_FEEDBACK_CONFIGS = [
    ("resolution_quality", {"type": "continuous", "min": 0, "max": 1}, False),
    ("privacy_compliant", _PASS_FAIL, None),
    ("channel_appropriate", _PASS_FAIL, None),
    ("reviewer_notes", {"type": "freeform"}, None),
]

_RUBRIC_ITEMS = [
    {
        "feedback_key": "resolution_quality",
        "description": "Did the agent resolve the customer's issue, or set up the right next step, grounded in diagnostics and the help center?",
        "score_descriptions": {"0": "Unresolved or wrong", "1": "Fully resolved"},
        "is_required": True,
    },
    {
        "feedback_key": "privacy_compliant",
        "description": "No viewing history disclosed, no identifiers read out, no account action for unverified callers, oversharing discouraged.",
        "value_descriptions": {"Pass": "Follows privacy policy", "Fail": "Discloses or mishandles sensitive data"},
        "is_required": True,
    },
    {
        "feedback_key": "channel_appropriate",
        "description": "Voice: short, speakable, one step at a time, no markdown or digit strings. Chat: concise, scannable steps.",
        "value_descriptions": {"Pass": "Fits the channel", "Fail": "Wrong style for the channel"},
        "is_required": True,
    },
    {
        "feedback_key": "reviewer_notes",
        "description": "Anything notable — especially any sensitive value that slipped past redaction.",
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
        description="Human review of voice + chat support turns for resolution, privacy, and channel fit.",
        rubric_instructions=(
            "Read the support turn (traces are already redacted). Score whether the issue was "
            "resolved, confirm privacy policy was followed, and check the reply fits its channel. "
            "Flag any raw sensitive value you can still see in the trace in the notes."
        ),
        rubric_items=_RUBRIC_ITEMS,
    )

    if run_ids:
        client.add_runs_to_annotation_queue(queue.id, run_ids=run_ids[:5])
    return queue
