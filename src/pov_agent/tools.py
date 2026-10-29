"""Tools for the smart-TV support agent.

Design choices that matter for sensitive data:

- **Identity comes from the session, not the conversation.** The channel (chat
  login or IVR phone + PIN) authenticates the customer and passes ``account_id``
  and ``identity_verified`` in graph state. Tools read them via ``ToolRuntime``,
  so the model never needs — and is never asked for — an email, phone number,
  or SSN to look someone up.
- **Unverified sessions get nothing account-specific.** Every account tool
  refuses when ``identity_verified`` is false. Only the public help center works.
- **Tools return realistic, over-shared payloads** (contact details, card on
  file, IP/MAC, device and household IDs, raw viewing events). That is
  intentional: real backends over-share, and the PII middleware's
  ``apply_to_tool_results`` is what keeps those values away from the model and
  the trace. Turn it off and watch the trace change.

All tools return JSON strings so the middleware's detectors see plain text.
"""

import hashlib
import json
from typing import Literal

from langchain.tools import ToolRuntime, tool

from pov_agent.support_data import ACCOUNTS, ACR_EVENTS, HELP_CENTER

_NOT_VERIFIED = {
    "error": "IDENTITY_NOT_VERIFIED",
    "instruction": (
        "The customer has not verified their identity on this channel. Do not discuss or "
        "change anything on the account. Ask them to verify: on voice, re-enter the account "
        "PIN when prompted; in chat, sign in to their account."
    ),
}


def _json(payload) -> str:
    return json.dumps(payload, indent=2)


def _session_account(runtime: ToolRuntime) -> tuple[str | None, dict | None]:
    state = runtime.state or {}
    if not state.get("identity_verified"):
        return None, None
    account_id = state.get("account_id")
    return account_id, ACCOUNTS.get(account_id)


def _find_device(account: dict, device_ref: str) -> dict | None:
    ref = (device_ref or "").strip().lower()
    devices = account["devices"]
    if len(devices) == 1 and not ref:
        return devices[0]
    for device in devices:
        haystack = f"{device['nickname']} {device['model']} {device['serial']}".lower()
        if ref and (ref in haystack or haystack.endswith(ref)):
            return device
    return None


def _ticket_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return f"{prefix}-{int(digest[:8], 16) % 90000 + 10000}"


@tool
def get_account_overview(runtime: ToolRuntime) -> str:
    """Look up the verified customer's account: contact details on file, registered TVs
    (nickname, model, firmware, warranty), and subscriptions. Call this first to learn
    which TVs the customer owns before troubleshooting or opening a ticket."""
    account_id, account = _session_account(runtime)
    if account is None:
        return _json(_NOT_VERIFIED)
    return _json(
        {
            "account_id": account_id,
            "full_name": account["full_name"],
            "email": account["email"],
            "phone": account["phone"],
            "address": account["address"],
            "card_on_file": account["card_on_file"],
            "subscriptions": account["subscriptions"],
            "devices": [
                {k: d[k] for k in ("nickname", "model", "serial", "firmware",
                                   "warranty_status", "warranty_ends")}
                for d in account["devices"]
            ],
        }
    )


@tool
def get_device_diagnostics(device_ref: str, runtime: ToolRuntime) -> str:
    """Pull live diagnostics for one of the customer's TVs: online status, firmware vs.
    latest available, Wi-Fi signal, and recent error codes.

    Args:
        device_ref: Which TV — its nickname (e.g. "Living Room"), screen size or model
            (e.g. "55"), or the last four characters of its serial.
    """
    _, account = _session_account(runtime)
    if account is None:
        return _json(_NOT_VERIFIED)
    device = _find_device(account, device_ref)
    if device is None:
        return _json(
            {
                "error": "DEVICE_NOT_FOUND",
                "devices_on_account": [d["nickname"] for d in account["devices"]],
            }
        )
    return _json(
        {k: device[k] for k in (
            "nickname", "model", "serial", "status", "firmware", "latest_firmware",
            "wifi_signal_dbm", "recent_error_codes", "warranty_status", "warranty_ends",
            "reported_symptom_notes", "ip_address", "mac_address", "device_id",
        )}
    )


@tool
def search_help_center(query: str) -> str:
    """Search the public help center for troubleshooting steps and policies. Works
    without identity verification.

    Args:
        query: What the customer needs help with, in plain words (e.g. "wifi drops",
            "pair remote", "turn off viewing data").
    """
    q = query.lower()
    scored = []
    for article in HELP_CENTER:
        score = sum(1 for kw in article["keywords"] if kw in q)
        score += sum(1 for word in q.split() if len(word) > 3 and word in article["title"].lower())
        if score:
            scored.append((score, article))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [{k: a[k] for k in ("id", "title", "steps", "url")} for _, a in scored[:2]]
    return _json({"results": results} if results else {"results": [], "note": "No matching article."})


@tool
def get_viewing_data_status(runtime: ToolRuntime) -> str:
    """Check the customer's Viewing Data (ACR) setting: whether collection is on, when
    they consented, and what categories of data are collected. Use for privacy questions
    about what the TV tracks."""
    _, account = _session_account(runtime)
    if account is None:
        return _json(_NOT_VERIFIED)
    events = ACR_EVENTS.get(account["household_id"], [])
    return _json(
        {
            "household_id": account["household_id"],
            "collection_enabled": account["viewing_data"]["collection_enabled"],
            "consented_on": account["viewing_data"]["consented_on"],
            "data_categories": [
                "content recognized on screen (title, network, genre)",
                "time and duration watched",
                "device and household identifiers",
                "IP address and approximate location",
            ],
            "events_on_file": len(events),
            "recent_events": events,
        }
    )


@tool
def set_viewing_data_collection(enabled: bool, runtime: ToolRuntime) -> str:
    """Turn Viewing Data (ACR) collection on or off for every TV on the account. Only
    call this when the customer has clearly asked for the change.

    Args:
        enabled: False to stop collection (opt out), True to resume it (opt in).
    """
    account_id, account = _session_account(runtime)
    if account is None:
        return _json(_NOT_VERIFIED)
    was = account["viewing_data"]["collection_enabled"]
    return _json(
        {
            "status": "unchanged" if was == enabled else "updated",
            "collection_enabled": enabled,
            "applies_to": [d["nickname"] for d in account["devices"]],
            "effective": "immediately; TVs pick up the change within 24 hours",
            "note": "Stopping collection does not delete data already collected. "
                    "Use submit_privacy_request(request_type='delete') for that.",
            "confirmation": _ticket_id("VD", account_id, str(enabled)),
        }
    )


@tool
def submit_privacy_request(request_type: Literal["access", "delete"], runtime: ToolRuntime) -> str:
    """File a formal privacy request for the verified account holder: 'access' sends
    them a secure copy of their data (including viewing history); 'delete' erases
    collected data. Use this instead of reading any personal data to the customer.

    Args:
        request_type: "access" for a copy of their data, "delete" to erase it.
    """
    account_id, account = _session_account(runtime)
    if account is None:
        return _json(_NOT_VERIFIED)
    return _json(
        {
            "request_id": _ticket_id("PR", account_id, request_type),
            "request_type": request_type,
            "status": "submitted",
            "completes_within_days": 45,
            "delivery": f"secure link sent to {account['email']}"
            if request_type == "access" else "confirmation sent to the email on file",
        }
    )


@tool
def create_support_ticket(
    category: Literal["repair", "warranty_replacement", "billing", "other"],
    summary: str,
    runtime: ToolRuntime,
    device_ref: str = "",
) -> str:
    """Open a ticket for work support can't finish in this conversation: repairs,
    warranty replacements, billing corrections, or escalations.

    Args:
        category: "repair" (out of warranty, paid), "warranty_replacement" (covered),
            "billing", or "other".
        summary: One or two sentences describing the issue. Describe the problem only —
            never include contact details, card numbers, or other identifiers.
        device_ref: Which TV the ticket is about (nickname, size, or serial last four),
            if any.
    """
    account_id, account = _session_account(runtime)
    if account is None:
        return _json(_NOT_VERIFIED)
    device = _find_device(account, device_ref) if device_ref else None
    payload = {
        "ticket_id": _ticket_id("CS", account_id, category, device_ref),
        "category": category,
        "device": device["nickname"] if device else None,
        "status": "open",
    }
    if category == "warranty_replacement" and device and device["warranty_status"] != "active":
        payload["warning"] = "Device is out of warranty; reclassified as a paid repair."
        payload["category"] = "repair"
    if payload["category"] == "repair":
        payload["quote_usd"] = 149.00
        payload["next_step"] = "A technician will call within 2 business days to schedule."
    elif category == "warranty_replacement":
        payload["next_step"] = "A prepaid shipping box arrives in 3-5 business days."
    elif category == "billing":
        payload["next_step"] = "Billing reviews within 5 business days; refunds go to the card on file."
    return _json(payload)


SUPPORT_TOOLS = [
    get_account_overview,
    get_device_diagnostics,
    search_help_center,
    get_viewing_data_status,
    set_viewing_data_collection,
    submit_privacy_request,
    create_support_ticket,
]
