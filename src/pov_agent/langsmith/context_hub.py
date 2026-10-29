"""Push the agent's prompt, memory, and skill into the LangSmith Context Hub.

Layout created:
  - skill repo  ``support-playbook``          -> SKILL.md
  - agent repo  ``pov-support-agent``         -> system_prompt.md, AGENTS.md,
                                                 and a link to the skill repo at
                                                 skills/support-playbook
The agent (``agent.py``) mounts the agent repo as its filesystem via
ContextHubBackend, read-only: the support team edits these files here; the agent
never writes to them, so no customer data can land in the Hub.
"""

from langsmith.schemas import FileEntry, SkillEntry

from pov_agent.config import AGENT_REPO, HUB_CONTENT_DIR, SKILL_REPO

_AGENT_README = (
    "Voice + chat customer support agent for a smart-TV brand (LangSmith POC). This repo "
    "holds the agent's system prompt, its team-curated memory (`AGENTS.md`), and a link to "
    "the `support-playbook` skill. Edit these here to change the agent without a redeploy. "
    "The agent has read-only access, so customer data is never written back."
)


def _read(*parts: str) -> str:
    return HUB_CONTENT_DIR.joinpath(*parts).read_text()


def push_context_hub(client) -> None:
    client.push_skill(
        SKILL_REPO,
        files={"SKILL.md": FileEntry(content=_read("skills", SKILL_REPO, "SKILL.md"))},
        description="Smart-TV support playbook: troubleshooting flows, Viewing Data (ACR) privacy policy, identity rules, ticket types.",
    )
    client.push_agent(
        AGENT_REPO,
        files={
            "system_prompt.md": FileEntry(content=_read("system_prompt.md")),
            "AGENTS.md": FileEntry(content=_read("AGENTS.md")),
            f"skills/{SKILL_REPO}": SkillEntry(repo_handle=SKILL_REPO),
        },
        description="POC voice + chat support agent: system prompt, memory, and linked playbook skill.",
        readme=_AGENT_README,
    )
