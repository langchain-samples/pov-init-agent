"""The smart-TV customer support deep agent (voice + chat).

Sensitive-data controls, in the order a request meets them:

  Level 1 — PII middleware (``privacy.build_pii_middleware``) on the main agent
            AND on the general-purpose subagent. Deep Agents auto-adds a
            general-purpose subagent that does NOT inherit user middleware, so
            we override it explicitly; otherwise ``task`` would be a side door
            around the redaction. It also gets no customer-data tools (least
            privilege).
  Level 2 — LLM Gateway, when enabled in ``config.get_model``.
  Level 3 — SDK masking: ``install_trace_masking`` makes an anonymizing
            LangSmith client the process default, so every trace from this
            process is scrubbed before egress.

Filesystem backend = a CompositeBackend that routes the agent's durable files
(system prompt, /AGENTS.md memory, /skills/) to the LangSmith Context Hub and
its ephemeral paths to an in-memory StateBackend. Writes to the Hub are denied:
a direct write to LangSmith bypasses both the gateway and SDK masking, so a
support agent that touches customer data must not persist anything there.
Memory and skills are curated by people in the Context Hub instead.
"""

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, ContextHubBackend, StateBackend
from deepagents.middleware import FilesystemPermission
from langsmith import Client

from pov_agent.channels import ChannelMiddleware
from pov_agent.config import AGENT_REPO, HUB_CONTENT_DIR, get_model
from pov_agent.privacy import build_pii_middleware, install_trace_masking
from pov_agent.tools import SUPPORT_TOOLS

_EPHEMERAL_ROUTES = ("/scratch/", "/large_tool_results/", "/conversation_history/")

_GENERAL_PURPOSE_PROMPT = (
    "You are a helper for a TV customer support agent. Complete the delegated task "
    "using only the information you are given. You have no access to customer "
    "accounts. Never repeat contact details, payment details, device identifiers, "
    "or viewing history."
)


def _system_prompt() -> str:
    """Prefer the Context Hub copy; fall back to the bundled file."""
    try:
        entry = Client().pull_agent(AGENT_REPO).files["system_prompt.md"]
        content = getattr(entry, "content", None) or entry["content"]
        if content:
            return content
    except Exception:
        pass
    return (HUB_CONTENT_DIR / "system_prompt.md").read_text()


def build_agent():
    install_trace_masking()

    backend = CompositeBackend(
        default=ContextHubBackend(AGENT_REPO),
        routes={route: StateBackend() for route in _EPHEMERAL_ROUTES},
    )
    permissions = [
        FilesystemPermission(
            operations=["write"], paths=[f"{r}**" for r in _EPHEMERAL_ROUTES], mode="allow"
        ),
        FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
    ]

    return create_deep_agent(
        model=get_model(),
        tools=SUPPORT_TOOLS,
        system_prompt=_system_prompt(),
        middleware=[ChannelMiddleware(), *build_pii_middleware()],
        subagents=[
            {
                "name": "general-purpose",
                "description": "General helper for drafting or reasoning tasks that need no account access.",
                "system_prompt": _GENERAL_PURPOSE_PROMPT,
                "tools": [],
                "middleware": build_pii_middleware(),
            }
        ],
        backend=backend,
        permissions=permissions,
        skills=["/skills/"],
        memory=["/AGENTS.md"],
    ).with_config({"recursion_limit": 50})


agent = build_agent()
