"""Voice + chat from one graph.

The session fields the channel supplies travel in graph state, alongside the
messages:

    {"messages": [...], "channel": "voice" | "chat",
     "account_id": "ACC-1001", "identity_verified": true}

``ChannelMiddleware`` contributes those fields to the agent's state schema and,
on every model call, appends the style rules for the active channel plus a
short session line to the system prompt. ``account_id`` is deliberately NOT put
in the prompt — tools read it from state, so the model never handles it.
"""

from typing import Literal, NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import SystemMessage

from pov_agent.config import CHAT_STYLE, VOICE_STYLE


class SupportState(AgentState):
    channel: NotRequired[Literal["voice", "chat"]]
    account_id: NotRequired[str]
    identity_verified: NotRequired[bool]


def channel_instructions(state: dict) -> str:
    channel = state.get("channel") or "chat"
    verified = bool(state.get("identity_verified"))
    style = VOICE_STYLE if channel == "voice" else CHAT_STYLE
    session = (
        f"## Session\nchannel={channel}; identity_verified={'yes' if verified else 'no'}. "
        + (
            "The customer is authenticated; account tools will work."
            if verified
            else "The customer is NOT verified. Help with general questions only; "
            "do not discuss or change anything on an account."
        )
    )
    return f"{style}\n\n{session}"


def _with_channel(request):
    addition = channel_instructions(request.state or {})
    current = request.system_message
    if current is None:
        return request.override(system_message=SystemMessage(content=addition))
    content = current.content
    if isinstance(content, str):
        new_content = f"{content}\n\n{addition}"
    else:
        new_content = [*content, {"type": "text", "text": addition}]
    return request.override(system_message=SystemMessage(content=new_content))


class ChannelMiddleware(AgentMiddleware):
    """Adds session fields to state and channel-specific style to the prompt."""

    state_schema = SupportState

    def wrap_model_call(self, request, handler):
        return handler(_with_channel(request))

    async def awrap_model_call(self, request, handler):
        return await handler(_with_channel(request))
