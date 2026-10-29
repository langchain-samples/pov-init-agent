"""One way to drive the agent, shared by seed traces, offline evals, and notebooks.

A support "turn" is described by a flat dict — the same shape as a dataset
example's inputs:

    {"channel": "voice", "account_id": "ACC-1001", "identity_verified": True,
     "message": "<customer message or STT transcript>"}
"""

import uuid

from langchain_core.messages import AIMessage

from pov_agent.config import ACTION_TOOLS

DEEPAGENTS_INTERNAL_TOOLS = {
    "write_todos", "read_todos", "ls", "glob", "grep", "read_file", "write_file", "edit_file",
}


def turn_input(inputs: dict) -> dict:
    return {
        "messages": [{"role": "user", "content": inputs["message"]}],
        "channel": inputs.get("channel", "chat"),
        "account_id": inputs.get("account_id"),
        "identity_verified": bool(inputs.get("identity_verified", False)),
    }


def final_text(result: dict) -> str:
    messages = result.get("messages", [])
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not message.tool_calls:
            content = message.content
            if isinstance(content, list):
                content = " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                )
            if content and content.strip():
                return content
    return ""


def tools_called(result: dict) -> list[str]:
    """Domain tools the main agent called, in order (deep-agent file tools excluded)."""
    names = []
    for message in result.get("messages", []):
        for tc in getattr(message, "tool_calls", None) or []:
            if tc["name"] not in DEEPAGENTS_INTERNAL_TOOLS:
                names.append(tc["name"])
    return names


def action_calls(result: dict) -> list[dict]:
    """Action-tool calls with their arguments (e.g. what went into a ticket summary)."""
    calls = []
    for message in result.get("messages", []):
        for tc in getattr(message, "tool_calls", None) or []:
            if tc["name"] in ACTION_TOOLS:
                calls.append({"name": tc["name"], "args": tc.get("args", {})})
    return calls


def run_turn(agent, inputs: dict, *, metadata: dict | None = None, tags: list[str] | None = None) -> dict:
    """Invoke the agent for one turn; return {response, tools_called, actions, action_calls}."""
    config = {
        "configurable": {"thread_id": str(uuid.uuid4())},
        "metadata": {"channel": inputs.get("channel", "chat"), **(metadata or {})},
        "tags": [inputs.get("channel", "chat"), *(tags or [])],
    }
    result = agent.invoke(turn_input(inputs), config=config)
    called = tools_called(result)
    return {
        "response": final_text(result),
        "tools_called": called,
        "actions": sorted({name for name in called if name in ACTION_TOOLS}),
        "action_calls": action_calls(result),
    }
