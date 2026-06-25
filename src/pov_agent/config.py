"""Shared configuration: model selection and the names of every LangSmith object.

Everything the bootstrap creates is named here so it's easy to find in your
workspace and trivial to rename for a second run.
"""

import os
from pathlib import Path

from langchain.chat_models import init_chat_model

# ── Model (provider-agnostic) ────────────────────────────────────────────────
# "provider:model" — switch providers by changing MODEL in .env, nothing else.
DEFAULT_MODEL = "anthropic:claude-sonnet-4-6"


def get_model():
    """The chat model used by both the agent and the LLM-as-judge evaluator."""
    return init_chat_model(os.environ.get("MODEL", DEFAULT_MODEL))


# ── LangSmith object names ───────────────────────────────────────────────────
AGENT_REPO = "pov-report-writer"        # Context Hub agent repo (prompt + memory + skill link)
SKILL_REPO = "report-style-guide"       # Context Hub skill repo
DATASET_NAME = "pov-report-writer-eval"  # golden topics for offline eval
QUEUE_NAME = "pov-report-review"         # human annotation queue
ONLINE_EVALUATOR_NAME = "report-structure"  # online code evaluator on live traces

# Tracing project the agent's runs land in (overridable via .env).
PROJECT = os.environ.get("LANGSMITH_PROJECT", "pov-report-writer")

# ── House report structure ───────────────────────────────────────────────────
# The sections a well-formed report must contain. Used by the structure metric
# (offline + online) and described to the agent in the skill / system prompt.
EXPECTED_SECTIONS = [
    "executive summary",
    "background",
    "key findings",
    "recommendations",
    "conclusion",
]

HUB_CONTENT_DIR = Path(__file__).parent / "langsmith" / "hub_content"
