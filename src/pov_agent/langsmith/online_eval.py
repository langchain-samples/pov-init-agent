"""Online code evaluator — runs server-side on live production traces.

Uploaded with:
    langsmith evaluator upload online_eval.py --function perform_eval \
        --name channel-format --project <project> --sampling-rate 1.0

Scores whether each live reply fits its channel (voice = speakable, chat =
concise). It reads the channel from the root run's inputs ({"channel": ...}).

Constraints of the online code-evaluator sandbox: the function takes exactly one
positional ``run`` argument, has NO network access, may use only the standard
library plus numpy/pandas/scipy/scikit-learn/jsonschema, and does not keep
module-level helpers in scope at call time. It therefore CANNOT import this
repo, so the rule below is duplicated from ``score_channel_format()`` in
``evaluators.py`` and everything lives inside ``perform_eval``.

Note: online evaluators see traces AFTER SDK masking, so this evaluator never
touches raw customer data.

# ponytail: deliberate duplication — the sandbox forbids importing repo code.
# If you change the channel rules here, change score_channel_format() too.
"""


def perform_eval(run):
    import re

    voice_max_words = 75
    chat_max_words = 200
    markdown_re = re.compile(
        r"(^\s*#{1,6}\s)|(\*\*)|(^\s*[-*•]\s)|(^\s*\d+[.)]\s)|(`)|(\|.*\|)", re.MULTILINE
    )
    url_re = re.compile(r"https?://|www\.", re.IGNORECASE)
    digit_run_re = re.compile(r"\d{3,}")

    def final_reply(run):
        outputs = (run or {}).get("outputs") or {}
        for message in reversed(outputs.get("messages") or []):
            if not isinstance(message, dict):
                continue
            if message.get("type") not in (None, "ai", "AIMessage", "AIMessageChunk"):
                continue
            if message.get("tool_calls"):
                continue
            content = message.get("content")
            if isinstance(content, list):
                content = " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                )
            if isinstance(content, str) and content.strip():
                return content
        return outputs.get("response", "") if isinstance(outputs.get("response"), str) else ""

    inputs = (run or {}).get("inputs") or {}
    channel = inputs.get("channel") or "chat"
    text = final_reply(run)
    if not text.strip():
        return {"channel_format": 0.0}

    words = len(text.split())
    if channel == "voice":
        checks = [
            not markdown_re.search(text),
            not url_re.search(text),
            not digit_run_re.search(text),
            ">" not in text,
            words <= voice_max_words,
        ]
    else:
        checks = [words <= chat_max_words]
    return {"channel_format": round(sum(checks) / len(checks), 3)}
