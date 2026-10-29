"""Shared configuration: model selection, channel rules, and the names of every
LangSmith object.

Everything the bootstrap creates is named here so it's easy to find in your
workspace and trivial to rename for a second run.
"""

import os
from pathlib import Path

from langchain.chat_models import init_chat_model

# ── Model (provider-agnostic) ────────────────────────────────────────────────
# "provider:model" — switch providers by changing MODEL in .env, nothing else.
# Default to a cheap "nano" tier so the eval suite (many agent + judge calls) is
# affordable to demo.
DEFAULT_MODEL = "openai:gpt-5.4-nano"

# PHI/PII control Level 2 — the LangSmith LLM Gateway. It is OpenAI-compatible:
# point an OpenAI-provider client at this base URL and authenticate with a
# LangSmith key. With PII redaction enabled on the gateway (workspace settings),
# sensitive values in the outbound request are swapped for
# [SAFE_TO_USE:CATEGORY_xxxxxxxx] placeholders before they reach the provider,
# and restored on the way back. Spend limits are enforced at the same layer.
LANGSMITH_GATEWAY_URL = os.environ.get(
    "LANGSMITH_GATEWAY_URL", "https://gateway.smith.langchain.com/openai"
)


def get_model():
    """The chat model used by both the agent and the LLM-as-judge evaluators.

    Routes through the LangSmith LLM Gateway by default so every model call
    (agent + judges) gets centralized spend limits and gateway-side PII
    redaction — the only control that survives misconfigured app code, because
    it is enforced at the network layer. Set USE_LANGSMITH_GATEWAY=false in .env
    to fall back to a direct provider call.
    """
    model = os.environ.get("MODEL", DEFAULT_MODEL)
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


# ── LangSmith object names ───────────────────────────────────────────────────
AGENT_REPO = "pov-support-agent"             # Context Hub agent repo (prompt + memory + skill link)
SKILL_REPO = "support-playbook"              # Context Hub skill repo
DATASET_NAME = "pov-support-agent-eval"      # golden support conversations for offline eval
PRODUCTION_DATASET_NAME = "pov-support-agent-production-samples"  # sampled live traces, for labeling
QUEUE_NAME = "pov-support-review"            # human annotation queue
ONLINE_EVALUATOR_NAME = "channel-format"     # online code evaluator on live traces

# Tracing project the agent's runs land in (overridable via .env).
PROJECT = os.environ.get("LANGSMITH_PROJECT", "pov-support-agent")

HUB_CONTENT_DIR = Path(__file__).parent / "langsmith" / "hub_content"

# ── Channels ─────────────────────────────────────────────────────────────────
# The agent serves two channels from one graph. Voice input arrives as a
# speech-to-text transcript; voice output is handed to a text-to-speech layer,
# so it must be speakable. The channel is part of the graph input
# ({"channel": "voice" | "chat", ...}) and steers the reply style per turn.
CHANNELS = ("voice", "chat")

# Limits enforced by the channel-format evaluator (offline + online). The
# online evaluator duplicates these because its sandbox can't import the repo.
VOICE_MAX_WORDS = 75
CHAT_MAX_WORDS = 200

VOICE_STYLE = """## Channel: VOICE
Your reply is read aloud by text-to-speech. The customer's message is a speech-to-text
transcript and may contain misheard words.
- Plain spoken sentences only. No markdown, bullets, numbered lists, headings, tables,
  emoji, or URLs.
- Keep it short: at most three sentences (about 60 words). Give one troubleshooting step
  at a time, then check in.
- Say numbers the way a person speaks them. Read codes character by character in words
  (for example "ticket C S four eight two one three"). Never write a run of three or
  more digits.
- Say menu paths in words ("go to Settings, then Network, then Network Status"). Never
  use symbols like ">" or "/" that a speech engine would read aloud.
- The caller may not be alone. Never read out contact details, payment details, device
  identifiers, or anything about what was watched.
- If something in the transcript is ambiguous, confirm it before taking an action."""

CHAT_STYLE = """## Channel: CHAT
Your reply is shown in a chat widget.
- Light markdown is fine: numbered steps for troubleshooting, bold for menu paths.
- Keep it under about 150 words. Link help-center articles returned by search.
- Never echo raw identifiers back (contact details, card numbers, device identifiers),
  even if the customer typed them."""

# Tools that change something for the customer. Used by the action-correctness
# and channel-parity evaluators (read-only lookups are excluded).
ACTION_TOOLS = (
    "set_viewing_data_collection",
    "submit_privacy_request",
    "create_support_ticket",
)
