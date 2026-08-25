"""Shared configuration: model selection and the names of every LangSmith object.

Everything the bootstrap creates is named here so it's easy to find in your
workspace and trivial to rename for a second run.
"""

import os
from pathlib import Path

from langchain.chat_models import init_chat_model

# ── Model (provider-agnostic) ────────────────────────────────────────────────
# "provider:model" — switch providers by changing MODEL in .env, nothing else.
# Default to a cheap "nano" tier so the eval suite (many agent + judge calls) is
# affordable to demo. Bump to openai:gpt-5.1 (or gpt-5-nano) via MODEL in .env
# when you want higher-fidelity reviews.
DEFAULT_MODEL = "openai:gpt-5.4-nano"
# DEFAULT_MODEL = "openai:gpt-5-nano"

# The LangSmith LLM Gateway is OpenAI-compatible: point an OpenAI-provider client
# at this base URL and authenticate with the LangSmith API key. The gateway then
# fans out to whatever provider connection your workspace has for the model id.
LANGSMITH_GATEWAY_URL = "https://gateway.smith.langchain.com/openai"


def get_model():
    """The chat model used by both the agent and the LLM-as-judge evaluator.

    Routes through the LangSmith LLM Gateway by default so a single LangSmith key
    covers every model call (agent + judges) with centralized spend controls. Set
    USE_LANGSMITH_GATEWAY=false in .env to fall back to a direct provider call.
    """
    model = os.environ.get("MODEL", DEFAULT_MODEL)
    use_gateway = os.environ.get("USE_LANGSMITH_GATEWAY", "true").lower() == "true"

    if use_gateway:
        api_key = os.environ.get("LANGSMITH_API_KEY_GATEWAY") or os.environ["LANGSMITH_API_KEY_GATEWAY"]
        # The gateway addresses models by bare id (no "provider:" prefix).
        model_name = model.split(":", 1)[-1]
        # An org-scoped LangSmith key must name its workspace; the gateway reads it
        # from the X-Tenant-ID header. Workspace-scoped keys don't need this.
        workspace_id = os.environ.get("LANGSMITH_WORKSPACE_ID_GATEWAY")
        # extra = {"default_headers": {"X-Tenant-ID": workspace_id}} if workspace_id else {}
        return init_chat_model(
            model_name,
            model_provider="openai",
            base_url=LANGSMITH_GATEWAY_URL,
            api_key=api_key,
            # **extra,
        )

    return init_chat_model(model)


# ── LangSmith object names ───────────────────────────────────────────────────
AGENT_REPO = "pov-job-matcher"          # Context Hub agent repo (prompt + memory + skill link)
SKILL_REPO = "match-rubric-guide"       # Context Hub skill repo
DATASET_NAME = "pov-job-matcher-eval"   # golden resume/JD pairs for offline eval
QUEUE_NAME = "pov-match-review"          # human annotation queue
ONLINE_EVALUATOR_NAME = "match-structure"  # online code evaluator on live traces

# Tracing project the agent's runs land in (overridable via .env).
PROJECT = os.environ.get("LANGSMITH_PROJECT", "pov-job-matcher")

# ── House review structure ───────────────────────────────────────────────────
# The sections a well-formed match review must contain. Used by the structure
# metric (offline + online) and described to the agent in the skill / prompt.
EXPECTED_SECTIONS = [
    "match summary",
    "strengths",
    "gaps",
    "recommendation",
]

# ── Fairness configuration ───────────────────────────────────────────────────
# Protected attributes we perturb in the counterfactual-fairness evaluator. Each
# entry is (label, [variant_a, variant_b, ...]) — swapping between variants must
# not move the agent's match score by more than MATCH_SCORE_TOLERANCE.
PROTECTED_ATTRIBUTE_SWAPS = {
    "name": [
        "Jordan Miller",
        "Lakisha Washington",
        "Wei Chen",
        "Mohammed Al-Farsi",
    ],
    "pronouns": ["he/him", "she/her", "they/them"],
}

# Max allowed absolute difference in match score between counterfactual variants
# of the SAME resume. Bigger swings mean the agent is keying on a protected
# attribute instead of the candidate's qualifications.
MATCH_SCORE_TOLERANCE = 0.10

HUB_CONTENT_DIR = Path(__file__).parent / "langsmith" / "hub_content"
