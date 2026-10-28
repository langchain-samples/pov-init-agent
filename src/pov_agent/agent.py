"""The docs-assistant deep agent.

Answers questions about an internal AI platform — its docs and how to run things
on it — by searching a bundled docs corpus (``tools.py``) and citing what it used.

Filesystem backend = a CompositeBackend that routes:
  - the agent's durable files (/AGENTS.md memory, /skills/) to the LangSmith Context
    Hub (the default backend, mounted at /), and
  - the deep agent's noisy, ephemeral paths to an in-memory StateBackend so they
    never create Context Hub commits.

``local_context=True`` swaps the Context Hub for a throwaway local copy of
``hub_content/`` — hermetic, so the CI eval gate needs no Context Hub repo and can't
write memory back to it.

Each agent version is one git-tracked file (``agent_versions/<version>.md``: the
system prompt plus front matter saying whether it gets the docs tools, skill, and
memory), selected by the repo-root ``AGENT_VERSION`` file. A push that changes the
version or its file is exactly what the CI eval gate scores.
"""

import shutil
import tempfile

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, ContextHubBackend, FilesystemBackend, StateBackend

from pov_agent.config import AGENT_REPO, HUB_CONTENT_DIR, get_model, load_agent_version
from pov_agent.tools import TOOLS


def _local_hub_copy() -> FilesystemBackend:
    root = tempfile.mkdtemp(prefix="pov-hub-")
    shutil.copytree(HUB_CONTENT_DIR, root, dirs_exist_ok=True)
    return FilesystemBackend(root_dir=root, virtual_mode=True)


def build_agent(version: str | None = None, local_context: bool = False):
    spec = load_agent_version(version)
    version = spec["version"]
    durable = _local_hub_copy() if local_context else ContextHubBackend(AGENT_REPO)
    backend = CompositeBackend(
        default=durable,
        routes={
            "/scratch/": StateBackend(),
            "/large_tool_results/": StateBackend(),     # deep-agent internal offloads
            "/conversation_history/": StateBackend(),   # deep-agent internal offloads
        },
    )
    return create_deep_agent(
        model=get_model(),
        tools=TOOLS if spec["tools"] else [],
        system_prompt=spec["system_prompt"],
        backend=backend,
        skills=["/skills/"] if spec["skills"] else None,
        memory=["/AGENTS.md"] if spec["memory"] else None,
        name=f"docs-assistant-{version}",
    ).with_config({"recursion_limit": 50, "metadata": {"agent_version": version}})


def final_text(result: dict) -> str:
    """The text of the agent's last message."""
    messages = result.get("messages", [])
    if not messages:
        return ""
    content = messages[-1].content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content or ""


def ask(agent, question: str, **config) -> str:
    """Ask the agent one question and return its final answer text."""
    return final_text(agent.invoke({"messages": [{"role": "user", "content": question}]}, config=config or None))


agent = build_agent()
