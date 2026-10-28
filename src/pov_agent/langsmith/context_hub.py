"""Push the agent's prompt, memory, and skill into the LangSmith Context Hub.

Layout created:
  - skill repo  ``docs-answer-guide``            -> SKILL.md
  - agent repo  ``pov-docs-assistant``           -> system_prompt.md, AGENTS.md,
                                                    and a link to the skill repo at
                                                    skills/docs-answer-guide
The agent (``agent.py``) mounts the agent repo as its filesystem via ContextHubBackend
and reads its skill + memory from it. The system prompt itself is versioned in git
(``agent_versions/``) so the CI eval gate scores exactly what was pushed; the Hub copy
mirrors the active version for visibility.
"""

from langsmith.schemas import FileEntry, SkillEntry

from pov_agent.config import AGENT_REPO, HUB_CONTENT_DIR, SKILL_REPO, load_agent_version

_AGENT_README = (
    "Platform docs assistant for the LangSmith POC: answers questions about Nimbus AI Platform "
    "and how to run things on it. This repo holds the agent's system prompt (mirrored from git), "
    "its long-term memory (`AGENTS.md`), and a link to the `docs-answer-guide` skill. Edit the "
    "memory or skill here to change the agent without a redeploy."
)


def _read(*parts: str) -> str:
    return HUB_CONTENT_DIR.joinpath(*parts).read_text()


def push_context_hub(client) -> None:
    client.push_skill(
        SKILL_REPO,
        files={"SKILL.md": FileEntry(content=_read("skills", SKILL_REPO, "SKILL.md"))},
        description="House style for platform docs answers: search-then-answer, step format, citations, equal treatment.",
    )
    client.push_agent(
        AGENT_REPO,
        files={
            "system_prompt.md": FileEntry(content=load_agent_version()["system_prompt"]),
            "AGENTS.md": FileEntry(content=_read("AGENTS.md")),
            f"skills/{SKILL_REPO}": SkillEntry(repo_handle=SKILL_REPO),
        },
        description="POC docs assistant: system prompt, memory, and linked answer-guide skill.",
        readme=_AGENT_README,
    )
