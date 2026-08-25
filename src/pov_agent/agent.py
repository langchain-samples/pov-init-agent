"""The resume-to-job match deep agent.

Filesystem backend = a CompositeBackend that routes:
  - the agent's durable files (system prompt, /AGENTS.md memory, /skills/) to the
    LangSmith Context Hub, which is the default backend (mounted at /), and
  - the deep agent's noisy, ephemeral paths to an in-memory StateBackend so they
    never create Context Hub commits.

The system prompt lives in the Context Hub (source of truth). We pull it at
construction and fall back to the bundled copy so `langgraph dev` works before
you've run the bootstrap.
"""

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, ContextHubBackend, StateBackend
from langsmith import Client

from pov_agent.config import AGENT_REPO, HUB_CONTENT_DIR, get_model


def _system_prompt() -> str:
    """Prefer the Context Hub copy; fall back to the bundled file."""
    try:
        entry = Client().pull_agent(AGENT_REPO).files["system_prompt.md"]
        # AgentContext file entries expose .content; tolerate a plain dict too.
        content = getattr(entry, "content", None) or entry["content"]
        if content:
            return content
    except Exception:
        pass
    return (HUB_CONTENT_DIR / "system_prompt.md").read_text()


def build_agent():
    hub = ContextHubBackend(AGENT_REPO)
    backend = CompositeBackend(
        default=hub,
        routes={
            "/scratch/": StateBackend(),               # section drafts — ephemeral
            "/large_tool_results/": StateBackend(),     # deep-agent internal offloads
            "/conversation_history/": StateBackend(),   # deep-agent internal offloads
        },
    )
    return create_deep_agent(
        model=get_model(),
        system_prompt=_system_prompt(),
        backend=backend,
        skills=["/skills/"],
        memory=["/AGENTS.md"],
    ).with_config({"recursion_limit": 50})  # backstop; default is effectively unbounded


agent = build_agent()
