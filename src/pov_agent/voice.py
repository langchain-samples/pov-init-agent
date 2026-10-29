"""Real audio for voice turns: caller audio → speech-to-text → agent → text-to-speech.

Each voice turn is traced as one ``voice_call`` with three children:

    voice_call                   call_recording attached (caller + agent, one file)
    ├── speech_to_text           caller audio → transcript   (gpt-4o-mini-transcribe)
    ├── <agent graph>            transcript → reply text     (the support agent)
    └── text_to_speech           reply text → reply audio    (gpt-4o-mini-tts)

Seed "caller" audio is synthesized once from each scenario's message with a TTS
voice and cached on disk (``voice_fixtures/``), so re-runs only pay for STT and
the reply TTS. All audio is 16-bit PCM WAV so clips can be stitched with the
standard library.

Audio and the sensitive-data controls
-------------------------------------
Every control in ``privacy.py`` works on text. None of them can redact audio: a
recording of a caller reading out a card number is stored as-is, and a voice
can identify the person speaking. So:

- **Caller audio is NOT attached to traces by default.** It is transcribed
  in-process and only the transcript goes into the trace (where SDK masking
  scrubs it) and to the agent (where the PII middleware scrubs it). With
  ``ATTACH_CALLER_AUDIO=false`` the top-level recording is the agent's reply
  only. ``ATTACH_CALLER_AUDIO=true`` attaches the full call (caller + agent) —
  only ever enable it for synthetic audio like this repo's fixtures.
- **The agent's reply audio IS attached.** It is synthesized from the reply
  text after the PII middleware has already redacted it, so it contains
  nothing the redacted trace doesn't.
"""

import hashlib
import io
import os
import struct
import wave
from pathlib import Path

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from langsmith.schemas import Attachment

from pov_agent.runner import run_turn

STT_MODEL = os.environ.get("STT_MODEL", "gpt-4o-mini-transcribe")
TTS_MODEL = os.environ.get("TTS_MODEL", "gpt-4o-mini-tts")
CALLER_VOICE = "ash"     # the synthetic customer
AGENT_VOICE = "coral"    # the support agent
FIXTURE_DIR = Path(__file__).parent / "langsmith" / "voice_fixtures"
PAUSE_SECONDS = 0.7      # gap between caller and agent in the stitched recording
AUDIO_TIMEOUT_SECONDS = 60

_AGENT_INSTRUCTIONS = "Warm, calm customer-support voice. Natural pace."
_CALLER_INSTRUCTIONS = "A customer calling a TV support line, casual and a little frustrated."


def attach_caller_audio() -> bool:
    return os.environ.get("ATTACH_CALLER_AUDIO", "false").lower() == "true"


def voice_audio_enabled() -> bool:
    return os.environ.get("VOICE_AUDIO", "true").lower() == "true"


def _openai_client():
    """OpenAI client for audio endpoints (STT/TTS).

    Uses OPENAI_API_KEY when set; otherwise falls back to the LangSmith LLM
    Gateway (OpenAI-compatible) with the LangSmith key.
    """
    from openai import OpenAI

    from pov_agent.config import LANGSMITH_GATEWAY_URL

    # Audio calls occasionally stall; the SDK default (600s + retries) would
    # freeze a whole bootstrap on one clip.
    limits = {"timeout": AUDIO_TIMEOUT_SECONDS, "max_retries": 2}
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAI(**limits)
    api_key = os.environ.get("LANGSMITH_API_KEY_GATEWAY") or os.environ.get("LANGSMITH_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Voice audio needs OPENAI_API_KEY or a LangSmith key for the gateway. "
            "Set one in .env, or set VOICE_AUDIO=false to run voice turns as text."
        )
    return OpenAI(base_url=LANGSMITH_GATEWAY_URL, api_key=api_key, **limits)


def synthesize(text: str, *, voice: str, instructions: str) -> bytes:
    response = _openai_client().audio.speech.create(
        model=TTS_MODEL, voice=voice, input=text, instructions=instructions, response_format="wav"
    )
    return response.content


def transcribe(audio: bytes, filename: str = "call.wav") -> str:
    result = _openai_client().audio.transcriptions.create(model=STT_MODEL, file=(filename, audio))
    return result.text


# ── WAV helpers ───────────────────────────────────────────────────────────────
def _read_pcm(wav_bytes: bytes) -> tuple[tuple[int, int, int], bytes]:
    """Return ((channels, sample_width, rate), pcm_frames) from a PCM WAV.

    Parses the RIFF chunks directly instead of using ``wave``: streamed TTS
    WAVs often carry a placeholder data-chunk length, so the data chunk is
    read to the end of the file.
    """
    if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        raise ValueError("not a WAV file")
    pos, params = 12, None
    while pos + 8 <= len(wav_bytes):
        chunk_id = wav_bytes[pos:pos + 4]
        size = struct.unpack("<I", wav_bytes[pos + 4:pos + 8])[0]
        body = pos + 8
        if chunk_id == b"fmt ":
            _, channels, rate, _, _, bits = struct.unpack("<HHIIHH", wav_bytes[body:body + 16])
            params = (channels, bits // 8, rate)
        elif chunk_id == b"data":
            if params is None:
                raise ValueError("WAV data chunk before fmt chunk")
            end = len(wav_bytes) if body + size > len(wav_bytes) else body + size
            return params, wav_bytes[body:end]
        pos = body + size + (size % 2)
    raise ValueError("WAV has no data chunk")


def _write_wav(params: tuple[int, int, int], pcm: bytes) -> bytes:
    channels, width, rate = params
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.setframerate(rate)
        out.writeframes(pcm)
    return buffer.getvalue()


def stitch(*clips: bytes, pause_seconds: float = PAUSE_SECONDS) -> bytes:
    """Concatenate WAV clips (same format) with a short silence between them."""
    decoded = [_read_pcm(c) for c in clips]
    params = decoded[0][0]
    if any(p != params for p, _ in decoded):
        raise ValueError(f"clip formats differ: {[p for p, _ in decoded]}")
    channels, width, rate = params
    silence = b"\x00" * (int(rate * pause_seconds) * channels * width)
    return _write_wav(params, silence.join(pcm for _, pcm in decoded))


def caller_audio(fixture_id: str, message: str) -> bytes:
    """Cached synthetic caller audio for a scenario (generated on first use)."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURE_DIR / f"{fixture_id}.wav"
    if not path.exists():
        path.write_bytes(synthesize(message, voice=CALLER_VOICE, instructions=_CALLER_INSTRUCTIONS))
    return path.read_bytes()


# ── Traced pipeline ───────────────────────────────────────────────────────────
def _drop(*keys):
    return lambda payload: {k: v for k, v in payload.items() if k not in keys}


def _wav_attachment(data: bytes) -> Attachment:
    return Attachment(mime_type="audio/wav", data=data)


@traceable(name="speech_to_text", run_type="tool", process_inputs=_drop("audio"))
def _speech_to_text(audio: bytes, model: str, audio_bytes: int) -> dict:
    run = get_current_run_tree()
    if run is not None and attach_caller_audio():
        run.attachments["caller_audio"] = _wav_attachment(audio)
    return {"transcript": transcribe(audio)}


@traceable(name="text_to_speech", run_type="tool", process_outputs=_drop("audio"))
def _text_to_speech(text: str, model: str, voice: str) -> dict:
    audio = synthesize(text, voice=voice, instructions=_AGENT_INSTRUCTIONS)
    run = get_current_run_tree()
    if run is not None:
        run.attachments["reply_audio"] = _wav_attachment(audio)
    return {"audio": audio, "audio_bytes": len(audio), "voice": voice}


@traceable(name="voice_call", run_type="chain", process_inputs=_drop("agent", "audio", "metadata"))
def voice_call(agent, *, channel: str, account_id: str, identity_verified: bool,
               audio: bytes, metadata: dict | None = None) -> dict:
    """One phone call turn. Inputs recorded on the trace: channel + session fields
    (never the raw audio). Outputs: transcript, reply text, actions. Attachment:
    ``call_recording`` — caller + agent when ATTACH_CALLER_AUDIO=true, else the
    agent's reply only."""
    stt = _speech_to_text(audio, STT_MODEL, len(audio))
    turn = run_turn(
        agent,
        {"channel": channel, "account_id": account_id,
         "identity_verified": identity_verified, "message": stt["transcript"]},
        metadata={"audio": True, **(metadata or {})},
    )
    if turn["response"]:
        try:
            reply_audio = _text_to_speech(turn["response"], TTS_MODEL, AGENT_VOICE)["audio"]
        except Exception as exc:  # a failed clip shouldn't fail the turn; the trace records the error
            print(f"   (reply audio skipped: {type(exc).__name__}: {exc})")
            reply_audio = None
        if reply_audio:
            recording = stitch(audio, reply_audio) if attach_caller_audio() else reply_audio
            run = get_current_run_tree()
            if run is not None:
                run.attachments["call_recording"] = _wav_attachment(recording)
    return {"transcript": stt["transcript"], **turn}


def run_voice_or_text_turn(agent, inputs: dict, *, metadata: dict | None = None) -> dict:
    """Voice inputs go through the audio pipeline (when enabled); chat inputs and
    VOICE_AUDIO=false run as plain text turns."""
    if inputs.get("channel") != "voice" or not voice_audio_enabled():
        return run_turn(agent, inputs, metadata=metadata)
    fixture_id = hashlib.sha256(inputs["message"].encode()).hexdigest()[:12]
    return voice_call(
        agent,
        channel="voice",
        account_id=inputs.get("account_id"),
        identity_verified=bool(inputs.get("identity_verified")),
        audio=caller_audio(fixture_id, inputs["message"]),
        metadata=metadata,
        langsmith_extra={
            "metadata": {"channel": "voice", "audio": True, **(metadata or {})},
            "tags": ["voice", "audio"],
        },
    )


def _demo() -> None:
    """Self-check for the WAV stitching (no network)."""
    params = (1, 2, 24000)
    a = _write_wav(params, b"\x01\x00" * 24000)   # 1.0 s
    b = _write_wav(params, b"\x02\x00" * 12000)   # 0.5 s
    # Simulate a streamed WAV whose data-chunk length is a placeholder.
    streamed = a[:40] + struct.pack("<I", 0xFFFFFFFF) + a[44:]
    joined_params, pcm = _read_pcm(stitch(streamed, b))
    assert joined_params == params
    expected_frames = 24000 + int(24000 * PAUSE_SECONDS) + 12000
    assert len(pcm) == expected_frames * 2, (len(pcm), expected_frames * 2)
    print("voice self-check passed")


if __name__ == "__main__":
    _demo()
