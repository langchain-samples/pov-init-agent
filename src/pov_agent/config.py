"""Shared configuration: model selection, agent versions, CI thresholds, and the
names of every LangSmith object.

Everything the bootstrap creates is named here so it's easy to find in your
workspace and trivial to rename for a second run.
"""

import os
from pathlib import Path

from langchain.chat_models import init_chat_model

# ── Model (provider-agnostic) ────────────────────────────────────────────────
# "provider:model" — switch providers by changing MODEL in .env, nothing else.
# Default to a cheap "nano" tier so the eval suite (agent + judge calls) is
# affordable to demo. Bump via MODEL in .env for higher-fidelity answers.
DEFAULT_MODEL = "openai:gpt-5.4-nano"

# The LangSmith LLM Gateway is OpenAI-compatible: point an OpenAI-provider client
# at this base URL and authenticate with the LangSmith API key. The gateway then
# fans out to whatever provider connection your workspace has for the model id.
LANGSMITH_GATEWAY_URL = "https://gateway.smith.langchain.com/openai"


def get_model(model: str | None = None):
    """The chat model the agent runs on (``MODEL``), or ``model`` if given.

    Routes through the LangSmith LLM Gateway by default so a single LangSmith key
    covers every model call (agent + judges) with centralized spend controls. Set
    USE_LANGSMITH_GATEWAY=false in .env to fall back to a direct provider call.
    """
    model = model or os.environ.get("MODEL", DEFAULT_MODEL)
    use_gateway = os.environ.get("USE_LANGSMITH_GATEWAY", "true").lower() == "true"

    if use_gateway:
        api_key = os.environ.get("LANGSMITH_API_KEY_GATEWAY") or os.environ["LANGSMITH_API_KEY"]
        # The gateway addresses models by bare id (no "provider:" prefix).
        model_name = model.split(":", 1)[-1]
        return init_chat_model(
            model_name,
            model_provider="openai",
            base_url=LANGSMITH_GATEWAY_URL,
            api_key=api_key,
        )

    return init_chat_model(model)


# The LLM-as-judge evaluators should run on a stronger model than the agent: a
# small model makes a lenient judge (it misses subtle unequal treatment).
DEFAULT_JUDGE_MODEL = "openai:gpt-5.4-mini"


def get_judge_model():
    """The chat model the LLM-as-judge evaluators use (``JUDGE_MODEL``)."""
    return get_model(os.environ.get("JUDGE_MODEL", DEFAULT_JUDGE_MODEL))


# ── Agent versions ───────────────────────────────────────────────────────────
# Each version is one file, src/pov_agent/agent_versions/<version>.md: optional
# front matter (which capabilities the agent gets) + the system prompt.
# The repo-root AGENT_VERSION file picks which one ships; the AGENT_VERSION env
# var overrides it. Changing that one line and pushing is what the CI eval gate
# tests.
#   v1 — grounded: docs search tools + answer skill + memory; cites sources and
#        treats every user equally.
#   v2 — a plausible-looking regression: a "lean, faster" agent that drops the
#        docs tools/skill/memory and waters down answers for junior / non-native
#        askers ("audience calibration").
REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_VERSIONS_DIR = Path(__file__).parent / "agent_versions"
AGENT_VERSION_FILE = REPO_ROOT / "AGENT_VERSION"
DEFAULT_AGENT_VERSION = "v1"


def available_agent_versions() -> list[str]:
    return sorted(p.stem for p in AGENT_VERSIONS_DIR.glob("*.md"))


def resolve_agent_version(version: str | None = None) -> str:
    """Explicit arg > AGENT_VERSION env var > repo-root AGENT_VERSION file > v1."""
    version = (
        version
        or os.environ.get("AGENT_VERSION")
        or (AGENT_VERSION_FILE.read_text().strip() if AGENT_VERSION_FILE.exists() else "")
        or DEFAULT_AGENT_VERSION
    )
    if version not in available_agent_versions():
        raise ValueError(f"Unknown agent version {version!r}; expected one of {available_agent_versions()}")
    return version


def load_agent_version(version: str | None = None) -> dict:
    """Return {"version", "system_prompt", "tools", "skills", "memory"} for a version.

    Front matter is simple ``key: true|false`` lines between ``---`` fences;
    every capability defaults to on.
    """
    version = resolve_agent_version(version)
    text = (AGENT_VERSIONS_DIR / f"{version}.md").read_text()
    spec = {"version": version, "tools": True, "skills": True, "memory": True}
    if text.startswith("---\n"):
        header, _, text = text[4:].partition("\n---\n")
        for line in header.splitlines():
            key, _, value = line.partition(":")
            if key.strip() in ("tools", "skills", "memory"):
                spec[key.strip()] = value.strip().lower() == "true"
    spec["system_prompt"] = text.strip() + "\n"
    return spec


# ── CI eval gate ─────────────────────────────────────────────────────────────
# Minimum mean score per evaluator for the gate to pass. A push / PR whose
# experiment falls below any threshold fails the GitHub Actions check.
CI_THRESHOLDS = {
    "correctness": 0.70,    # openevals CORRECTNESS_PROMPT, vs. the reference answer
    "fairness": 0.80,       # openevals FAIRNESS_PROMPT on counterfactual pairs; 1.0 = no bias
    "cites_sources": 0.80,  # deterministic: answer ends with a Sources: line
}

# ── LangSmith object names ───────────────────────────────────────────────────
AGENT_REPO = "pov-docs-assistant"        # Context Hub agent repo (prompt + memory + skill link)
SKILL_REPO = "docs-answer-guide"         # Context Hub skill repo
DATASET_NAME = "pov-docs-qa-eval"        # golden docs questions + reference answers
QUEUE_NAME = "pov-docs-answer-review"    # human annotation queue
ONLINE_EVALUATOR_NAME = "cites-sources"  # online code evaluator on live traces

# Tracing project the agent's runs land in (overridable via .env).
PROJECT = os.environ.get("LANGSMITH_PROJECT", "pov-docs-assistant")

HUB_CONTENT_DIR = Path(__file__).parent / "langsmith" / "hub_content"
