"""Sensitive-data controls for the support agent.

This module implements the prevention layers from "Keeping sensitive data out of
LangSmith" that live in *your application code*:

  Level 1 — PII Middleware (``build_pii_middleware``)
      Runs inside the agent loop. Scrubs the customer's message, the model's
      output, AND tool results (the most commonly missed knob) before the model
      sees them and before the trace records them. This agent handles
      unstructured user input on an intake/routing surface, so the model should
      NOT see raw identifiers: it never needs a customer's email, card number,
      MAC address, or watch history to troubleshoot a TV.

  Level 3 — LangSmith SDK masking (``build_tracing_client`` /
      ``install_trace_masking``)
      Runs in-process right before trace egress. Catches what Level 1 can't:
      the raw graph input recorded on the root run, the raw model output before
      ``after_model`` rewrites it, and any non-agent code path.

Level 2 (the LLM Gateway) is a deployment toggle in ``config.get_model``.

Both levels share ONE set of detectors (``DETECTORS``) so a pattern added here
is enforced everywhere. The data shapes mirror smart-TV ACR (automatic content
recognition) viewer data: device and household identifiers, network
identifiers, coarse location, and viewing history — plus ordinary account PII.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from langchain.agents.middleware.pii import (
    PIIMatch,
    PIIMiddleware,
    detect_credit_card,
    detect_email,
    detect_ip,
    detect_mac_address,
)

Detector = Callable[[str], list[PIIMatch]]


def _regex_detector(pii_type: str, pattern: str, flags: int = 0, group: int = 0) -> Detector:
    """Build a detector from a regex. ``group`` selects which capture group is
    the sensitive span (so context like a JSON key can anchor the match without
    being redacted)."""
    compiled = re.compile(pattern, flags)

    def detect(content: str) -> list[PIIMatch]:
        return [
            PIIMatch(type=pii_type, value=m.group(group), start=m.start(group), end=m.end(group))
            for m in compiled.finditer(content)
        ]

    detect.__name__ = f"detect_{pii_type}"
    return detect


_DIGIT_WORD = r"(?:zero|oh|one|two|three|four|five|six|seven|eight|nine)"

# ── Detectors (shared by Level 1 and Level 3) ────────────────────────────────
# Order matters for Level 1: each type is its own middleware and they run in
# sequence, so longer numeric patterns (cards) are handled before shorter ones
# (phones) can match inside them.
DETECTORS: dict[str, Detector] = {
    "credit_card": detect_credit_card,
    "ssn": _regex_detector("ssn", r"\b\d{3}-\d{2}-\d{4}\b"),
    "email": detect_email,
    "us_phone": _regex_detector(
        "us_phone", r"(?<![\w-])(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?![\w-])"
    ),
    # Voice-specific: STT engines often transcribe spoken numbers as words
    # ("four one five five five five ..."). Seven or more digit-words in a row
    # is a phone or card number read aloud.
    "spoken_number": _regex_detector(
        "spoken_number", rf"\b(?:{_DIGIT_WORD}[\s,.-]+){{6,}}{_DIGIT_WORD}\b", re.IGNORECASE
    ),
    "street_address": _regex_detector(
        "street_address",
        r"\b\d{1,6}\s+(?:[A-Z][a-z]+\s+){1,3}"
        r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Ln|Lane|Dr|Drive|Ct|Court|Way|Pl|Place)\b\.?",
    ),
    "ip": detect_ip,
    "mac_address": detect_mac_address,
    # ACR identifiers. Device/advertising IDs are UUIDs; household IDs are
    # HH-######. Hashing (Level 1) lets the model correlate without seeing them.
    "device_id": _regex_detector(
        "device_id",
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    "household_id": _regex_detector("household_id", r"\bHH-\d{6}\b"),
    # TV serial numbers, e.g. QX65A2210457. Masked to the last four so the
    # agent and customer can still tell two TVs apart.
    "tv_serial": _regex_detector("tv_serial", r"\b[A-Z]{2}\d{2}[A-Z]\d{7}\b"),
    "geo_coordinates": _regex_detector(
        "geo_coordinates", r"-?\d{1,3}\.\d{3,}\s*,\s*-?\d{1,3}\.\d{3,}"
    ),
    # Viewing history: the title field in ACR records returned by tools.
    # Anchored on the JSON key so only the title value is redacted.
    "viewing_history": _regex_detector(
        "viewing_history", r'"(?:content_title|program_title)"\s*:\s*"([^"]+)"', group=1
    ),
}

# Level 1 strategy per type. `redact` replaces with [REDACTED_TYPE]; `mask`
# keeps the last four characters; `hash` swaps in a stable digest so the model
# can tell values apart without seeing them. `block` is deliberately unused: it
# raises and ends the conversation, which is the wrong UX for a support line.
STRATEGIES: dict[str, str] = {
    "credit_card": "mask",
    "ssn": "redact",
    "email": "redact",
    "us_phone": "redact",
    "spoken_number": "redact",
    "street_address": "redact",
    "ip": "redact",
    "mac_address": "redact",
    "device_id": "hash",
    "household_id": "hash",
    "tv_serial": "mask",
    "geo_coordinates": "redact",
    "viewing_history": "redact",
}


def _combined_detector(name: str, pii_types: list[str]) -> Detector:
    """One detector over several types. Each match keeps its own ``type`` (so
    placeholders stay specific, e.g. [REDACTED_EMAIL]); overlapping matches are
    dropped in favor of the earlier-listed type."""

    def detect(content: str) -> list[PIIMatch]:
        kept: list[PIIMatch] = []
        for pii_type in pii_types:
            for m in DETECTORS[pii_type](content):
                if all(m["end"] <= k["start"] or m["start"] >= k["end"] for k in kept):
                    kept.append(m)
        return kept

    detect.__name__ = f"detect_{name}"
    return detect


def build_pii_middleware() -> list[PIIMiddleware]:
    """Level 1: PII middleware applied to input, output, AND tool results.

    PIIMiddleware takes one detector + one strategy per instance, and every
    instance adds before/after-model nodes to the graph. Rather than one
    instance per type (13 instances = ~26 extra nodes per model call), types are
    grouped by strategy into three instances. Mask runs first so card numbers
    are handled before the phone pattern could see their digits.
    """
    groups: dict[str, list[str]] = {}
    for pii_type in DETECTORS:
        groups.setdefault(STRATEGIES[pii_type], []).append(pii_type)
    order = ("mask", "redact", "hash")
    return [
        PIIMiddleware(
            f"sensitive_{strategy}",
            detector=_combined_detector(strategy, groups[strategy]),
            strategy=strategy,
            apply_to_input=True,
            apply_to_output=True,
            apply_to_tool_results=True,
        )
        for strategy in order
        if strategy in groups
    ]


def find_sensitive(text: str) -> list[PIIMatch]:
    """Every raw sensitive value in ``text`` (used by the leak evaluator)."""
    matches: list[PIIMatch] = []
    for detector in DETECTORS.values():
        matches.extend(detector(text or ""))
    return matches


def redact_text(text: str) -> str:
    """Replace every detected value with ``[REDACTED_TYPE]``.

    Applied detector by detector (same order as Level 1) so overlapping
    patterns can't corrupt each other's offsets.
    """
    for pii_type, detector in DETECTORS.items():
        matches = detector(text)
        for m in sorted(matches, key=lambda x: x["start"], reverse=True):
            text = text[: m["start"]] + f"[REDACTED_{pii_type.upper()}]" + text[m["end"] :]
    return text


# ── Level 3: LangSmith SDK masking ───────────────────────────────────────────
# Structured fields that are always sensitive, whatever their value looks like.
# The anonymizer walks every string in a run's inputs/outputs; when the string
# sits under one of these keys, it's replaced wholesale.
SENSITIVE_KEYS = frozenset(
    {
        "email", "phone", "address", "street_address", "card_number", "card_on_file",
        "ip_address", "mac_address", "device_id", "advertising_id", "household_id",
        "serial", "serial_number", "latitude", "longitude", "content_title",
        "program_title", "full_name", "name_on_account",
    }
)


def trace_replacer(value: str, path: list[str | int]) -> str:
    """Path-aware replacer for ``langsmith.anonymizer.create_anonymizer``."""
    if path and isinstance(path[-1], str) and path[-1].lower() in SENSITIVE_KEYS:
        return f"[REDACTED_{path[-1].upper()}]"
    return redact_text(value)


def build_tracing_client(**kwargs):
    """A LangSmith Client that scrubs every run before it leaves the process."""
    from langsmith import Client
    from langsmith.anonymizer import create_anonymizer

    return Client(anonymizer=create_anonymizer(trace_replacer), **kwargs)


_installed_client = None


def install_trace_masking(client=None):
    """Make the masking client the process-wide default for tracing.

    LangChain/LangGraph tracers resolve their client through
    ``langsmith.run_trees.get_cached_client()``, which ``langsmith.configure``
    overrides — so every agent trace emitted from this process is anonymized,
    including ones from ``langgraph dev``. Idempotent: called with no argument,
    it reuses the client installed earlier.
    """
    import langsmith

    global _installed_client
    if client is None and _installed_client is not None:
        return _installed_client
    _installed_client = client or build_tracing_client()
    langsmith.configure(client=_installed_client)
    return _installed_client


def _demo() -> None:
    """Self-check for the detectors and the trace replacer."""
    assert redact_text("mail me at dana.w@example.com") == "mail me at [REDACTED_EMAIL]"
    assert "[REDACTED_US_PHONE]" in redact_text("call (415) 555-0142 tonight")
    assert "[REDACTED_SPOKEN_NUMBER]" in redact_text("it's four one five five five five zero one four two ok")
    assert "[REDACTED_SSN]" in redact_text("SSN 123-45-6789")
    assert "[REDACTED_CREDIT_CARD]" in redact_text("card 4111 1111 1111 1111")
    assert "[REDACTED_US_PHONE]" not in redact_text("card 4111 1111 1111 1111")
    assert "[REDACTED_STREET_ADDRESS]" in redact_text("ship to 2187 Larkspur Ave please")
    assert "[REDACTED_IP]" in redact_text("ip 192.168.1.44")
    assert "[REDACTED_MAC_ADDRESS]" in redact_text("mac 3C:52:A1:0F:9B:7E")
    assert "[REDACTED_HOUSEHOLD_ID]" in redact_text("HH-204918")
    assert "[REDACTED_TV_SERIAL]" in redact_text("serial QX65A2210457")
    assert "[REDACTED_DEVICE_ID]" in redact_text("id 6f1c2a9e-3b4d-4e5f-8a7b-9c0d1e2f3a4b")
    redacted = redact_text('{"content_title": "Late Night Live", "network": "NBC"}')
    assert '"content_title": "[REDACTED_VIEWING_HISTORY]"' in redacted and "NBC" in redacted
    assert redact_text("Firmware 4.2.1, error E-203, ticket CS-48213") == (
        "Firmware 4.2.1, error E-203, ticket CS-48213"
    )
    assert trace_replacer("anything", ["outputs", "email"]) == "[REDACTED_EMAIL]"
    assert trace_replacer("press Home", ["outputs", "content"]) == "press Home"
    assert len(build_pii_middleware()) == len(set(STRATEGIES.values()))
    mask = _combined_detector("mask", ["credit_card", "tv_serial"])
    assert {m["type"] for m in mask("card 4111 1111 1111 1111, TV QX65A2210457")} == {"credit_card", "tv_serial"}
    print("privacy self-check passed")


if __name__ == "__main__":
    _demo()
