"""Push the agent's prompt, memory, and skill into the LangSmith Context Hub.

Layout created:
  - skill repo  ``match-rubric-guide``           -> SKILL.md
  - agent repo  ``pov-job-matcher``              -> system_prompt.md, AGENTS.md,
                                                    and a link to the skill repo at
                                                    skills/match-rubric-guide
The agent (``agent.py``) mounts the agent repo as its filesystem via ContextHubBackend.
"""

from langsmith.schemas import FileEntry, SkillEntry

from pov_agent.config import AGENT_REPO, HUB_CONTENT_DIR, SKILL_REPO

_AGENT_README = (
    "Resume-to-job match agent for the LangSmith POC. This repo holds the agent's "
    "system prompt, its long-term memory (`AGENTS.md`), and a link to the "
    "`match-rubric-guide` skill. Edit these here to change the agent without a redeploy."
)


def _read(*parts: str) -> str:
    return HUB_CONTENT_DIR.joinpath(*parts).read_text()


def push_context_hub(client) -> None:
    client.push_skill(
        SKILL_REPO,
        files={"SKILL.md": FileEntry(content=_read("skills", SKILL_REPO, "SKILL.md"))},
        description="House rubric for resume-to-job match reviews: section order, scoring bands, and fairness rules.",
    )
    client.push_agent(
        AGENT_REPO,
        files={
            "system_prompt.md": FileEntry(content=_read("system_prompt.md")),
            "AGENTS.md": FileEntry(content=_read("AGENTS.md")),
            f"skills/{SKILL_REPO}": SkillEntry(repo_handle=SKILL_REPO),
        },
        description="POC job-match agent: system prompt, memory, and linked rubric skill.",
        readme=_AGENT_README,
    )
