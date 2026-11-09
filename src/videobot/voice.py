"""Narration: text -> speech audio + word-timed transcript.

Both voice backends return the same thing, an audio file and an `autcaptions.Transcript`,
so captions never depend on which voice was used.

* Edge (default, free, no account): Microsoft's online neural voices via `edge-tts`.
* Polly (optional): AWS Polly neural voices, if `boto3` and AWS credentials are set up.
  Use a voice name like "polly:Matthew".
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

from autcaptions import Transcript


def speak(text: str, out_mp3: Path, voice: str = "en-US-ChristopherNeural", rate: str = "+15%") -> Transcript:
    if voice.startswith("polly:"):
        transcript = _polly(text, out_mp3, voice.split(":", 1)[1], rate)
    else:
        transcript = asyncio.run(_edge(text, out_mp3, voice, rate))
    return transcript.restore_punctuation(text)


async def _edge(text: str, out_mp3: Path, voice: str, rate: str) -> Transcript:
    import edge_tts

    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    boundaries = []
    with open(out_mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                boundaries.append(chunk)
    return Transcript.from_edge_boundaries(boundaries)


def _polly(text: str, out_mp3: Path, voice: str, rate: str) -> Transcript:
    import boto3  # optional dependency: pip install "videobot[polly]"

    polly = boto3.client("polly")
    pct = 100 + int(rate.strip("%+") or 0) * (-1 if rate.startswith("-") else 1)
    ssml = f'<speak><prosody rate="{pct}%">{_xml(text)}</prosody></speak>'
    common = dict(TextType="ssml", Text=ssml, VoiceId=voice, Engine="neural")
    out_mp3.write_bytes(polly.synthesize_speech(OutputFormat="mp3", **common)["AudioStream"].read())
    marks = polly.synthesize_speech(OutputFormat="json", SpeechMarkTypes=["word"], **common)
    return Transcript.from_polly_marks(marks["AudioStream"].read().decode(), audio_duration=duration(out_mp3))


def _xml(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def voices(locale_prefix: str = "en") -> list[str]:
    import edge_tts

    all_ = asyncio.run(edge_tts.list_voices())
    return sorted(v["ShortName"] for v in all_ if v["Locale"].startswith(locale_prefix))


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])
