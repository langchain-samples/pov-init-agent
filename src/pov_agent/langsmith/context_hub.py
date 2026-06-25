"""Push the agent's prompt, memory, and skill into the LangSmith Context Hub.

Layout created:
  - skill repo  ``report-style-guide``           -> SKILL.md
  - agent repo  ``pov-report-writer``            -> system_prompt.md, AGENTS.md,
                                                    and a link to the skill repo at
                                                    skills/report-style-guide
The agent (``agent.py``) mounts the agent repo as its filesystem via ContextHubBackend.
"""

from langsmith.schemas import FileEntry, SkillEntry

from pov_agent.config import AGENT_REPO, HUB_CONTENT_DIR, SKILL_REPO

_AGENT_README = (
    "Report-writer deep agent for the LangSmith POC. This repo holds the agent's "
    "system prompt, its long-term memory (`AGENTS.md`), and a link to the "
    "`report-style-guide` skill. Edit these here to change the agent without a redeploy."
)


def _read(*parts: str) -> str:
    return HUB_CONTENT_DIR.joinpath(*parts).read_text()


def push_context_hub(client) -> None:
    client.push_skill(
        SKILL_REPO,
        files={"SKILL.md": FileEntry(content=_read("skills", SKILL_REPO, "SKILL.md"))},
        description="House style for research reports: section order, purpose, and length targets.",
    )
    client.push_agent(
        AGENT_REPO,
        files={
            "system_prompt.md": FileEntry(content=_read("system_prompt.md")),
            "AGENTS.md": FileEntry(content=_read("AGENTS.md")),
            f"skills/{SKILL_REPO}": SkillEntry(repo_handle=SKILL_REPO),
        },
        description="POC report-writer agent: system prompt, memory, and linked skill.",
        readme=_AGENT_README,
    )
